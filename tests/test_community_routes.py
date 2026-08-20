from datetime import datetime

import pytest

from src.models import Asset, Comment, Post, PostCategory, PostReport, PostTickerMention, UserModel
from src.services import community


@pytest.fixture()
def other_user(db):
    u = UserModel(username="vecina", email="vecina@example.com", password="s3cret-pw")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def admin(db):
    u = UserModel(username="moderador", email="mod@example.com", password="s3cret-pw")
    u.is_admin = True
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    return client


def _asset(db, symbol, exchange="TSX"):
    asset = Asset(
        symbol=symbol,
        yahoo_symbol=f"{symbol}.TO" if exchange == "TSX" else symbol,
        exchange=exchange,
        currency="CAD" if exchange == "TSX" else "USD",
        name=f"{symbol} Corp",
    )
    db.session.add(asset)
    db.session.commit()
    return asset


def _post(db, user, body="Cuerpo", title="Título", category=PostCategory.ANALYSIS,
          created_at=None):
    post = Post(
        user_id=user.id,
        title=title,
        body=body,
        category=category,
        created_at=created_at or datetime.utcnow(),
    )
    db.session.add(post)
    db.session.flush()
    community.sync_mentions(post)
    db.session.commit()
    return post


# ── Access control ───────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/community", "/community/posts/1"])
def test_community_requires_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ── Feed page ────────────────────────────────────────────────────────────

def test_feed_page_renders_posts_and_composer(auth_client, db, user):
    _post(db, user, title="¿Está el dividendo de BCE en riesgo?")

    response = auth_client.get("/community")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "¿Está el dividendo de BCE en riesgo?" in body
    assert "Comparte un análisis, noticia o duda" in body


def test_feed_page_shows_empty_state_without_posts(auth_client):
    body = auth_client.get("/community").get_data(as_text=True)
    assert "Todavía no hay publicaciones" in body


def test_htmx_request_returns_only_the_feed_fragment(auth_client, db, user):
    _post(db, user, title="Solo el feed")

    response = auth_client.get("/community", headers={"HX-Request": "true"})
    body = response.get_data(as_text=True)

    assert "Solo el feed" in body
    assert "<html" not in body
    assert "Comparte un análisis" not in body


def test_sidebar_ranks_the_most_mentioned_tickers(auth_client, db, user):
    _asset(db, "BCE")
    _post(db, user, body="$BCE preocupa")
    _post(db, user, body="$BCE de nuevo")

    body = auth_client.get("/community").get_data(as_text=True)
    assert "2 menciones esta semana" in body


def test_unknown_sort_falls_back_to_recent(auth_client, db, user):
    _post(db, user, title="Presente")
    response = auth_client.get("/community?sort=inventado")
    assert response.status_code == 200
    assert "Presente" in response.get_data(as_text=True)


# ── Creating posts ───────────────────────────────────────────────────────

def test_create_post_stores_mentions_and_redirects_to_it(auth_client, db, user):
    ry = _asset(db, "RY")

    response = auth_client.post("/community/posts", data={
        "title": "Rotando hacia bancos",
        "body": "Sumo $RY después de resultados.",
        "category": PostCategory.TRADES.value,
    }, follow_redirects=True)
    body = response.get_data(as_text=True)

    post = Post.query.one()
    assert post.category == PostCategory.TRADES
    assert [m.asset_id for m in PostTickerMention.query.all()] == [ry.id]
    # The body renders the mention as a link to the company page.
    assert '<a href="/stocks/TSX/RY" class="tick">$RY</a>' in body


def test_create_post_rejects_an_empty_body(auth_client, db):
    response = auth_client.post("/community/posts", data={
        "title": "Sin cuerpo", "body": "", "category": PostCategory.ANALYSIS.value,
    }, follow_redirects=True)

    assert Post.query.count() == 0
    assert "El mensaje no puede estar vacío." in response.get_data(as_text=True)


def test_create_post_is_rate_limited(auth_client, db, user):
    for _ in range(community.POST_RATE_LIMIT):
        _post(db, user)

    response = auth_client.post("/community/posts", data={
        "title": "Uno más", "body": "Cuerpo", "category": PostCategory.ANALYSIS.value,
    }, follow_redirects=True)

    assert Post.query.count() == community.POST_RATE_LIMIT
    assert "límite de" in response.get_data(as_text=True)


# ── Post page, editing and deleting ──────────────────────────────────────

def test_post_page_shows_the_thread(auth_client, db, user):
    post = _post(db, user, title="Hilo")
    db.session.add(Comment(post_id=post.id, user_id=user.id, body="Coincido",
                           created_at=datetime.utcnow()))
    db.session.commit()

    body = auth_client.get(f"/community/posts/{post.id}").get_data(as_text=True)
    assert "Hilo" in body
    assert "Coincido" in body
    assert "1 comentario" in body


def test_deleted_post_is_not_reachable(auth_client, db, user):
    post = _post(db, user)
    post.is_deleted = True
    db.session.commit()

    assert auth_client.get(f"/community/posts/{post.id}").status_code == 404


def test_author_can_edit_and_mentions_follow(auth_client, db, user):
    _asset(db, "RY")
    su = _asset(db, "SU")
    post = _post(db, user, body="Compro $RY")

    auth_client.post(f"/community/posts/{post.id}/edit", data={
        "title": "Cambié de idea",
        "body": "Mejor $SU",
        "category": PostCategory.TRADES.value,
    })

    assert post.title == "Cambié de idea"
    assert post.updated_at is not None
    assert [m.asset_id for m in PostTickerMention.query.all()] == [su.id]


def test_a_stranger_cannot_edit_someone_elses_post(client, db, user, other_user):
    post = _post(db, user)
    _login(client, other_user)

    response = client.post(f"/community/posts/{post.id}/edit", data={
        "title": "Secuestrado", "body": "x", "category": PostCategory.ANALYSIS.value,
    })

    assert response.status_code == 403
    assert post.title == "Título"


def test_an_admin_cannot_rewrite_someone_elses_post(client, db, user, admin):
    """Moderation is removal, never authorship — an admin editing another
    member's words would put text under their name that they never wrote."""
    post = _post(db, user)
    _login(client, admin)

    response = client.post(f"/community/posts/{post.id}/edit", data={
        "title": "Reescrito", "body": "x", "category": PostCategory.ANALYSIS.value,
    })

    assert response.status_code == 403
    assert post.title == "Título"


def test_author_deletion_is_soft(auth_client, db, user):
    post = _post(db, user)

    auth_client.post(f"/community/posts/{post.id}/delete")

    assert post.is_deleted is True
    assert post.deleted_by_id == user.id
    # The row survives so votes, comments and mentions stay referential.
    assert Post.query.count() == 1


def test_admin_can_delete_someone_elses_post(client, db, user, admin):
    post = _post(db, user)
    _login(client, admin)

    client.post(f"/community/posts/{post.id}/delete")

    assert post.is_deleted is True
    assert post.deleted_by_id == admin.id


def test_a_stranger_cannot_delete_someone_elses_post(client, db, user, other_user):
    post = _post(db, user)
    _login(client, other_user)

    assert client.post(f"/community/posts/{post.id}/delete").status_code == 403
    assert post.is_deleted is False


# ── Voting ───────────────────────────────────────────────────────────────

def test_vote_returns_the_updated_widget(auth_client, db, user):
    post = _post(db, user)

    response = auth_client.post(f"/community/posts/{post.id}/vote", data={"value": "1"})
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert f'id="post-actions-{post.id}"' in body
    assert "vote-on-up" in body


def test_vote_rejects_an_out_of_range_value(auth_client, db, user):
    post = _post(db, user)
    assert auth_client.post(f"/community/posts/{post.id}/vote", data={"value": "7"}).status_code == 400


# ── Comments ─────────────────────────────────────────────────────────────

def test_comment_is_created_and_shown(auth_client, db, user):
    post = _post(db, user)

    auth_client.post(f"/community/posts/{post.id}/comments", data={"body": "Buen punto"})

    assert Comment.query.filter_by(post_id=post.id).one().body == "Buen punto"


def test_comment_deletion_is_soft_and_hides_it(auth_client, db, user):
    post = _post(db, user)
    comment = Comment(post_id=post.id, user_id=user.id, body="Me arrepiento",
                      created_at=datetime.utcnow())
    db.session.add(comment)
    db.session.commit()

    auth_client.post(f"/community/comments/{comment.id}/delete", follow_redirects=True)

    assert comment.is_deleted is True
    body = auth_client.get(f"/community/posts/{post.id}").get_data(as_text=True)
    assert "Me arrepiento" not in body


def test_a_stranger_cannot_delete_someone_elses_comment(client, db, user, other_user):
    post = _post(db, user)
    comment = Comment(post_id=post.id, user_id=user.id, body="Mío",
                      created_at=datetime.utcnow())
    db.session.add(comment)
    db.session.commit()
    _login(client, other_user)

    assert client.post(f"/community/comments/{comment.id}/delete").status_code == 403
    assert comment.is_deleted is False


def test_comment_is_rate_limited(auth_client, db, user):
    post = _post(db, user)
    for _ in range(community.COMMENT_RATE_LIMIT):
        db.session.add(Comment(post_id=post.id, user_id=user.id, body="x",
                               created_at=datetime.utcnow()))
    db.session.commit()

    response = auth_client.post(f"/community/posts/{post.id}/comments",
                                data={"body": "uno más"}, follow_redirects=True)

    assert Comment.query.count() == community.COMMENT_RATE_LIMIT
    assert "límite de" in response.get_data(as_text=True)


# ── Reporting ────────────────────────────────────────────────────────────

def test_reporting_a_post_records_it_once(client, db, user, other_user):
    post = _post(db, user)
    _login(client, other_user)

    client.post(f"/community/posts/{post.id}/report", data={"reason": "spam"})
    client.post(f"/community/posts/{post.id}/report", data={"reason": "otra vez"})

    report = PostReport.query.one()
    assert report.user_id == other_user.id
    assert report.reason == "spam"


# ── Company feed ─────────────────────────────────────────────────────────

def test_asset_feed_returns_only_posts_mentioning_that_ticker(auth_client, db, user):
    ry = _asset(db, "RY")
    _asset(db, "SU")
    _post(db, user, title="Sobre el banco", body="Sumo $RY")
    _post(db, user, title="Sobre la petrolera", body="Sumo $SU")

    body = auth_client.get(f"/community/asset/{ry.id}").get_data(as_text=True)

    assert "Sobre el banco" in body
    assert "Sobre la petrolera" not in body


def test_asset_feed_empty_state_names_the_ticker(auth_client, db):
    ry = _asset(db, "RY")
    body = auth_client.get(f"/community/asset/{ry.id}").get_data(as_text=True)
    assert "Nadie habló de RY todavía" in body
