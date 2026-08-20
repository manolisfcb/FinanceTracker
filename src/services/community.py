"""Feed queries, ticker-mention parsing and rate limiting for /community."""

import re
from datetime import datetime, timedelta

from markupsafe import Markup, escape
from sqlalchemy import func

from src.extensions import db
from src.models import Asset, Comment, Post, PostCategory, PostTickerMention, Vote

# A mention is `$` plus a ticker: at least one letter first, then letters,
# digits, dot or dash (BRK.B, RY, ENB). The trailing boundary keeps `$SU,`
# and `$SU.` working while `$100` and a bare `$` never match.
_MENTION_RE = re.compile(r"\$([A-Za-z][A-Za-z0-9]{0,6}(?:[.\-][A-Za-z0-9]{1,4})?)\b")

# The same ticker can exist on more than one exchange (ENB trades on both TSX
# and NYSE). A Canadian-first product resolves the ambiguity towards Canada.
_EXCHANGE_PRIORITY = {"TSX": 0, "TSXV": 1, "US": 2}

SORTS = [
    ("recent", "Recientes"),
    ("top", "Más votados"),
    ("hot", "En alta"),
]
DEFAULT_SORT = "recent"

# "En alta" and the trending sidebar both look at the same window: a week is
# long enough that a quiet weekend doesn't empty the list, short enough that
# last month's thread doesn't sit at the top forever.
TRENDING_WINDOW_DAYS = 7

# Rate limit: enough for a genuinely chatty user, low enough that a script
# can't flood the feed. Counted over a rolling window, not per calendar hour.
POST_RATE_LIMIT = 5
POST_RATE_WINDOW = timedelta(hours=1)
COMMENT_RATE_LIMIT = 20
COMMENT_RATE_WINDOW = timedelta(hours=1)

MAX_TITLE_LENGTH = 160
MAX_BODY_LENGTH = 8000
MAX_COMMENT_LENGTH = 4000


def extract_ticker_symbols(body: str) -> list[str]:
    """Uppercased `$TICKER` symbols in `body`, in order, without duplicates."""
    seen = []
    for match in _MENTION_RE.finditer(body or ""):
        symbol = match.group(1).upper()
        if symbol not in seen:
            seen.append(symbol)
    return seen


def resolve_mentions(body: str) -> dict[str, Asset]:
    """Map each mentioned symbol to the asset it refers to.

    Symbols with no asset in the universe are simply absent from the result:
    a typo renders as plain text rather than as a link to nothing.
    """
    symbols = extract_ticker_symbols(body)
    if not symbols:
        return {}

    assets = Asset.query.filter(func.upper(Asset.symbol).in_(symbols)).all()
    resolved: dict[str, Asset] = {}
    for asset in assets:
        key = asset.symbol.upper()
        current = resolved.get(key)
        if current is None or _exchange_rank(asset) < _exchange_rank(current):
            resolved[key] = asset
    return resolved


def _exchange_rank(asset: Asset) -> int:
    return _EXCHANGE_PRIORITY.get(asset.exchange, 99)


def sync_mentions(post: Post) -> list[PostTickerMention]:
    """Rewrite a post's mention rows to match its current title and body.

    Title *and* body: "$RY sube el dividendo" as a headline is as much a
    mention as one in the text, and counting only the body would quietly
    undercount the trending ranking. Only the body is linkified, though —
    the title is itself a link to the post, and anchors cannot nest.

    Called on create *and* on edit: an edited post that drops a ticker must
    stop counting towards that ticker's trending score and stop appearing in
    its company feed.
    """
    resolved = resolve_mentions(f"{post.title}\n{post.body}")
    wanted = {asset.id for asset in resolved.values()}

    existing = {m.asset_id: m for m in PostTickerMention.query.filter_by(post_id=post.id).all()}
    for asset_id, mention in existing.items():
        if asset_id not in wanted:
            db.session.delete(mention)

    rows = []
    for asset_id in wanted:
        mention = existing.get(asset_id)
        if mention is None:
            mention = PostTickerMention(
                post_id=post.id, asset_id=asset_id, created_at=post.created_at
            )
            db.session.add(mention)
        rows.append(mention)
    return rows


def render_body(body: str, url_for_asset) -> Markup:
    """Escaped post body with `$TICKER` turned into a link to the company page.

    `url_for_asset(asset)` builds the href, so this stays independent of the
    route layout and is trivially testable. Unresolved symbols keep their
    literal `$XYZ` text.
    """
    resolved = resolve_mentions(body)
    out = []
    cursor = 0
    for match in _MENTION_RE.finditer(body or ""):
        asset = resolved.get(match.group(1).upper())
        if asset is None:
            continue
        out.append(escape(body[cursor:match.start()]))
        out.append(
            Markup('<a href="{href}" class="tick">${symbol}</a>').format(
                href=url_for_asset(asset), symbol=asset.symbol
            )
        )
        cursor = match.end()
    out.append(escape(body[cursor:]))
    return Markup("").join(out)


def visible_posts_query():
    """Base query for every read path: soft-deleted posts are never listed."""
    return Post.query.filter(Post.is_deleted.is_(False))


def _score_subquery():
    return (
        db.session.query(Vote.post_id.label("post_id"), func.sum(Vote.value).label("score"))
        .group_by(Vote.post_id)
        .subquery()
    )


def _comment_count_subquery():
    return (
        db.session.query(
            Comment.post_id.label("post_id"), func.count(Comment.id).label("comment_count")
        )
        .filter(Comment.is_deleted.is_(False))
        .group_by(Comment.post_id)
        .subquery()
    )


def feed(sort=DEFAULT_SORT, category=None, asset_id=None, limit=50):
    """Posts for the feed, already decorated with score and comment count.

    Returns dicts rather than model instances so the template never triggers
    a per-post query for its counters.
    """
    scores = _score_subquery()
    comments = _comment_count_subquery()

    query = (
        db.session.query(
            Post,
            func.coalesce(scores.c.score, 0).label("score"),
            func.coalesce(comments.c.comment_count, 0).label("comment_count"),
        )
        .outerjoin(scores, scores.c.post_id == Post.id)
        .outerjoin(comments, comments.c.post_id == Post.id)
        .filter(Post.is_deleted.is_(False))
    )

    if category is not None:
        query = query.filter(Post.category == category)
    if asset_id is not None:
        query = query.join(
            PostTickerMention, PostTickerMention.post_id == Post.id
        ).filter(PostTickerMention.asset_id == asset_id)

    if sort == "top":
        query = query.order_by(func.coalesce(scores.c.score, 0).desc(), Post.created_at.desc())
    elif sort == "hot":
        # "En alta" is "top, but only among what's still current" — a week-old
        # window keeps a highly-voted post from owning the tab forever.
        cutoff = datetime.utcnow() - timedelta(days=TRENDING_WINDOW_DAYS)
        query = query.filter(Post.created_at >= cutoff).order_by(
            (
                func.coalesce(scores.c.score, 0) + func.coalesce(comments.c.comment_count, 0)
            ).desc(),
            Post.created_at.desc(),
        )
    else:
        query = query.order_by(Post.created_at.desc())

    return [
        {"post": post, "score": int(score or 0), "comment_count": int(comment_count or 0)}
        for post, score, comment_count in query.limit(limit).all()
    ]


def post_score(post_id: int) -> int:
    return int(
        db.session.query(func.coalesce(func.sum(Vote.value), 0))
        .filter(Vote.post_id == post_id)
        .scalar()
        or 0
    )


def comment_count(post_id: int) -> int:
    return Comment.query.filter_by(post_id=post_id, is_deleted=False).count()


def user_votes(user_id, post_ids) -> dict[int, int]:
    """`{post_id: +1|-1}` for the posts this user has already voted on."""
    if not post_ids:
        return {}
    rows = Vote.query.filter(Vote.user_id == user_id, Vote.post_id.in_(list(post_ids))).all()
    return {row.post_id: row.value for row in rows}


def apply_vote(user_id, post_id, value: int) -> int:
    """Cast, flip or withdraw a vote; returns the post's new score.

    Voting the same way twice withdraws the vote — the arrow acts as a
    toggle, which is what a second click on an already-lit arrow means.
    """
    if value not in (1, -1):
        raise ValueError("A vote must be +1 or -1")

    existing = Vote.query.filter_by(user_id=user_id, post_id=post_id).first()
    if existing is None:
        db.session.add(
            Vote(user_id=user_id, post_id=post_id, value=value, created_at=datetime.utcnow())
        )
    elif existing.value == value:
        db.session.delete(existing)
    else:
        existing.value = value
    db.session.commit()
    return post_score(post_id)


def trending_assets(limit=4, days=TRENDING_WINDOW_DAYS):
    """Most-mentioned assets of the last `days`, for the sidebar ranking."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.session.query(Asset, func.count(PostTickerMention.id).label("mentions"))
        .join(PostTickerMention, PostTickerMention.asset_id == Asset.id)
        .join(Post, Post.id == PostTickerMention.post_id)
        .filter(Post.is_deleted.is_(False), PostTickerMention.created_at >= cutoff)
        .group_by(Asset.id)
        .order_by(func.count(PostTickerMention.id).desc(), Asset.symbol)
        .limit(limit)
        .all()
    )
    return [{"asset": asset, "mentions": int(mentions)} for asset, mentions in rows]


def rate_limited(user_id, model, limit, window) -> bool:
    """Whether the user has hit `limit` writes of `model` inside `window`."""
    cutoff = datetime.utcnow() - window
    count = model.query.filter(
        model.user_id == user_id, model.created_at >= cutoff
    ).count()
    return count >= limit


def parse_category(value) -> PostCategory | None:
    """Category from its enum value, or None for the unfiltered feed."""
    if not value:
        return None
    try:
        return PostCategory(value)
    except ValueError:
        return None
