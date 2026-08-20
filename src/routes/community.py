from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from src.extensions import db
from src.forms.PostForm import CommentForm, PostForm
from src.models import (
    Asset,
    Comment,
    CompanyEvent,
    CompanyEventKind,
    POST_CATEGORY_LABELS,
    POST_CATEGORY_STYLES,
    Post,
    PostCategory,
    PostReport,
)
from src.services import community

community_bp = Blueprint('community', __name__)

SIDEBAR_NEWS_LIMIT = 4


def _asset_url(asset):
    return url_for('stocks.get_stock_detail', exchange=asset.exchange, symbol=asset.symbol)


def _recent_dividend_news(limit=SIDEBAR_NEWS_LIMIT):
    """Latest dividend events across the whole universe, for the left rail.

    Unlike the inbox, this is not scoped to the user's holdings: the sidebar
    is context for the conversation, so a member with an empty portfolio
    should still see what the market is talking about.
    """
    return (
        CompanyEvent.query.filter(CompanyEvent.kind == CompanyEventKind.DIVIDEND)
        .order_by(CompanyEvent.published_at.desc())
        .limit(limit)
        .all()
    )


def _decorate(entries):
    """Attach rendered body and the current user's vote to each feed entry."""
    votes = community.user_votes(current_user.id, [e["post"].id for e in entries])
    for entry in entries:
        post = entry["post"]
        entry["rendered_body"] = community.render_body(post.body, _asset_url)
        entry["user_vote"] = votes.get(post.id, 0)
        entry["can_moderate"] = _can_moderate(post)
    return entries


def _can_moderate(item) -> bool:
    """Authors manage their own content; admins manage anyone's."""
    return item.user_id == current_user.id or bool(getattr(current_user, 'is_admin', False))


def _feed_context(sort, category, asset_id=None):
    entries = _decorate(community.feed(sort=sort, category=category, asset_id=asset_id))
    return {
        'entries': entries,
        'sorts': community.SORTS,
        'selected_sort': sort,
        'categories': POST_CATEGORY_LABELS,
        'category_styles': POST_CATEGORY_STYLES,
        'selected_category': category,
    }


@community_bp.route('/community', methods=['GET'])
@login_required
def community_page():
    sort = request.args.get('sort', community.DEFAULT_SORT)
    if sort not in {key for key, _ in community.SORTS}:
        sort = community.DEFAULT_SORT
    category = community.parse_category(request.args.get('category'))

    context = _feed_context(sort, category)
    if request.headers.get('HX-Request'):
        return render_template('partials/community_feed.html', **context)

    context.update(
        form=PostForm(category=(category.value if category else PostCategory.ANALYSIS.value)),
        recent_news=_recent_dividend_news(),
        trending=community.trending_assets(),
    )
    return render_template('community.html', **context)


@community_bp.route('/community/posts', methods=['POST'])
@login_required
def create_post():
    form = PostForm()
    if not form.validate_on_submit():
        for errors in form.errors.values():
            flash(errors[0], 'danger')
        return redirect(url_for('community.community_page'))

    if community.rate_limited(
        current_user.id, Post, community.POST_RATE_LIMIT, community.POST_RATE_WINDOW
    ):
        flash(
            f'Alcanzaste el límite de {community.POST_RATE_LIMIT} publicaciones por hora. '
            'Probá de nuevo más tarde.',
            'danger',
        )
        return redirect(url_for('community.community_page'))

    post = Post(
        user_id=current_user.id,
        title=form.title.data.strip(),
        body=form.body.data.strip(),
        category=PostCategory(form.category.data),
        created_at=datetime.utcnow(),
    )
    db.session.add(post)
    # The mention rows reference post.id, so the post must exist first.
    db.session.flush()
    community.sync_mentions(post)
    db.session.commit()

    flash('Publicación creada', 'success')
    return redirect(url_for('community.post_page', post_id=post.id))


def _get_visible_post(post_id) -> Post:
    post = community.visible_posts_query().filter(Post.id == post_id).first()
    if post is None:
        abort(404)
    return post


@community_bp.route('/community/posts/<int:post_id>', methods=['GET'])
@login_required
def post_page(post_id):
    post = _get_visible_post(post_id)
    comments = (
        Comment.query.filter_by(post_id=post.id, is_deleted=False)
        .order_by(Comment.created_at.asc())
        .all()
    )
    already_reported = (
        PostReport.query.filter_by(post_id=post.id, user_id=current_user.id).first() is not None
    )
    return render_template(
        'community_post.html',
        post=post,
        rendered_body=community.render_body(post.body, _asset_url),
        score=community.post_score(post.id),
        user_vote=community.user_votes(current_user.id, [post.id]).get(post.id, 0),
        comments=[
            {'comment': c, 'rendered_body': community.render_body(c.body, _asset_url),
             'can_moderate': _can_moderate(c)}
            for c in comments
        ],
        can_moderate=_can_moderate(post),
        categories=POST_CATEGORY_LABELS,
        category_styles=POST_CATEGORY_STYLES,
        comment_form=CommentForm(),
        already_reported=already_reported,
    )


@community_bp.route('/community/posts/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = _get_visible_post(post_id)
    if post.user_id != current_user.id:
        # Admins may remove a post but never rewrite someone else's words.
        abort(403)

    form = PostForm(obj=post)
    if request.method == 'GET':
        form.category.data = post.category.value
        return render_template(
            'community_post_form.html', form=form, post=post, categories=POST_CATEGORY_LABELS
        )

    if not form.validate_on_submit():
        for errors in form.errors.values():
            flash(errors[0], 'danger')
        return render_template(
            'community_post_form.html', form=form, post=post, categories=POST_CATEGORY_LABELS
        )

    post.title = form.title.data.strip()
    post.body = form.body.data.strip()
    post.category = PostCategory(form.category.data)
    post.updated_at = datetime.utcnow()
    community.sync_mentions(post)
    db.session.commit()

    flash('Publicación actualizada', 'success')
    return redirect(url_for('community.post_page', post_id=post.id))


@community_bp.route('/community/posts/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = _get_visible_post(post_id)
    if not _can_moderate(post):
        abort(403)

    post.is_deleted = True
    post.deleted_at = datetime.utcnow()
    post.deleted_by_id = current_user.id
    db.session.commit()

    flash('Publicación eliminada', 'success')
    return redirect(url_for('community.community_page'))


@community_bp.route('/community/posts/<int:post_id>/vote', methods=['POST'])
@login_required
def vote_post(post_id):
    post = _get_visible_post(post_id)
    try:
        value = int(request.form.get('value', 0))
    except (TypeError, ValueError):
        value = 0
    if value not in (1, -1):
        return {'message': 'A vote must be +1 or -1'}, 400

    score = community.apply_vote(current_user.id, post.id, value)
    return render_template(
        'partials/community_vote.html',
        post=post,
        score=score,
        user_vote=community.user_votes(current_user.id, [post.id]).get(post.id, 0),
        comment_count=community.comment_count(post.id),
    )


@community_bp.route('/community/posts/<int:post_id>/comments', methods=['POST'])
@login_required
def create_comment(post_id):
    post = _get_visible_post(post_id)
    form = CommentForm()
    if not form.validate_on_submit():
        for errors in form.errors.values():
            flash(errors[0], 'danger')
        return redirect(url_for('community.post_page', post_id=post.id))

    if community.rate_limited(
        current_user.id, Comment, community.COMMENT_RATE_LIMIT, community.COMMENT_RATE_WINDOW
    ):
        flash(
            f'Alcanzaste el límite de {community.COMMENT_RATE_LIMIT} comentarios por hora.',
            'danger',
        )
        return redirect(url_for('community.post_page', post_id=post.id))

    db.session.add(
        Comment(
            post_id=post.id,
            user_id=current_user.id,
            body=form.body.data.strip(),
            created_at=datetime.utcnow(),
        )
    )
    db.session.commit()
    return redirect(url_for('community.post_page', post_id=post.id))


@community_bp.route('/community/comments/<int:comment_id>/edit', methods=['POST'])
@login_required
def edit_comment(comment_id):
    comment = Comment.query.filter_by(id=comment_id, is_deleted=False).first_or_404()
    if comment.user_id != current_user.id:
        abort(403)

    body = (request.form.get('body') or '').strip()
    if not body:
        flash('El comentario no puede estar vacío.', 'danger')
    elif len(body) > community.MAX_COMMENT_LENGTH:
        flash('El comentario es demasiado largo.', 'danger')
    else:
        comment.body = body
        comment.updated_at = datetime.utcnow()
        db.session.commit()

    return redirect(url_for('community.post_page', post_id=comment.post_id))


@community_bp.route('/community/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.filter_by(id=comment_id, is_deleted=False).first_or_404()
    if not _can_moderate(comment):
        abort(403)

    comment.is_deleted = True
    comment.deleted_at = datetime.utcnow()
    comment.deleted_by_id = current_user.id
    db.session.commit()
    return redirect(url_for('community.post_page', post_id=comment.post_id))


@community_bp.route('/community/posts/<int:post_id>/report', methods=['POST'])
@login_required
def report_post(post_id):
    post = _get_visible_post(post_id)
    existing = PostReport.query.filter_by(post_id=post.id, user_id=current_user.id).first()
    if existing is None:
        db.session.add(
            PostReport(
                post_id=post.id,
                user_id=current_user.id,
                reason=(request.form.get('reason') or '').strip()[:255] or None,
                created_at=datetime.utcnow(),
            )
        )
        db.session.commit()

    # The same message either way: telling a user their report is a duplicate
    # leaks that they already reported it from another session, and there is
    # nothing they could do differently.
    flash('Gracias, el equipo va a revisar esta publicación.', 'success')
    return redirect(url_for('community.post_page', post_id=post.id))


@community_bp.route('/community/asset/<int:asset_id>', methods=['GET'])
@login_required
def asset_feed(asset_id):
    """Posts mentioning one asset — the company page's "Comunidad" tab."""
    asset = Asset.query.get_or_404(asset_id)
    sort = request.args.get('sort', community.DEFAULT_SORT)
    if sort not in {key for key, _ in community.SORTS}:
        sort = community.DEFAULT_SORT

    context = _feed_context(sort, None, asset_id=asset.id)
    context['asset'] = asset
    return render_template('partials/community_asset_feed.html', **context)
