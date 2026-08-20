from datetime import datetime, timedelta

import pytest

from src.models import Asset, Comment, Post, PostCategory, PostTickerMention, Vote
from src.services import community


def _asset(db, symbol, exchange="TSX", name=None):
    asset = Asset(
        symbol=symbol,
        yahoo_symbol=f"{symbol}.TO" if exchange == "TSX" else symbol,
        exchange=exchange,
        currency="CAD" if exchange == "TSX" else "USD",
        name=name or f"{symbol} Corp",
    )
    db.session.add(asset)
    db.session.commit()
    return asset


def _post(db, user, body="Sin tickers", title="Título", category=PostCategory.ANALYSIS,
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


# ── Mention parsing ──────────────────────────────────────────────────────

@pytest.mark.parametrize("body, expected", [
    ("Roto por $RY y $ENB", ["RY", "ENB"]),
    ("minúsculas $bce cuentan", ["BCE"]),
    ("$RY otra vez $RY", ["RY"]),
    ("cuesta $100 y $ nada", []),
    ("clase B: $BRK.B", ["BRK.B"]),
    ("puntuación $SU, y $T.", ["SU", "T"]),
])
def test_extract_ticker_symbols(body, expected):
    assert community.extract_ticker_symbols(body) == expected


def test_resolve_mentions_prefers_the_canadian_listing(db):
    tsx = _asset(db, "ENB", exchange="TSX")
    _asset(db, "ENB", exchange="US")

    assert community.resolve_mentions("Miro $ENB")["ENB"].id == tsx.id


def test_unknown_ticker_resolves_to_nothing(db):
    _asset(db, "RY")
    assert community.resolve_mentions("Miro $NOPE") == {}


def test_render_body_links_known_tickers_and_escapes_the_rest(db):
    _asset(db, "RY")
    html = str(community.render_body("<b>ojo</b> con $RY y $NOPE", lambda a: f"/x/{a.symbol}"))

    assert '<a href="/x/RY" class="tick">$RY</a>' in html
    assert "&lt;b&gt;ojo&lt;/b&gt;" in html
    # An unresolved symbol stays literal text rather than becoming a dead link.
    assert "$NOPE" in html and 'href="/x/NOPE"' not in html


def test_sync_mentions_drops_tickers_removed_by_an_edit(db, user):
    _asset(db, "RY")
    _asset(db, "SU")
    post = _post(db, user, body="Compro $RY y $SU")
    assert PostTickerMention.query.filter_by(post_id=post.id).count() == 2

    post.body = "Ahora solo $SU"
    community.sync_mentions(post)
    db.session.commit()

    remaining = PostTickerMention.query.filter_by(post_id=post.id).all()
    assert [m.asset.symbol for m in remaining] == ["SU"]


# ── Voting ───────────────────────────────────────────────────────────────

def test_vote_toggles_off_when_repeated(db, user):
    post = _post(db, user)

    assert community.apply_vote(user.id, post.id, 1) == 1
    assert community.apply_vote(user.id, post.id, 1) == 0
    assert Vote.query.filter_by(post_id=post.id).count() == 0


def test_vote_flips_instead_of_stacking(db, user):
    post = _post(db, user)

    community.apply_vote(user.id, post.id, 1)
    assert community.apply_vote(user.id, post.id, -1) == -1
    assert Vote.query.filter_by(post_id=post.id).count() == 1


def test_vote_rejects_values_other_than_plus_or_minus_one(db, user):
    post = _post(db, user)
    with pytest.raises(ValueError):
        community.apply_vote(user.id, post.id, 5)


# ── Feed ordering and filters ────────────────────────────────────────────

def test_recent_feed_is_newest_first(db, user):
    old = _post(db, user, title="viejo", created_at=datetime.utcnow() - timedelta(days=2))
    new = _post(db, user, title="nuevo")

    assert [e["post"].id for e in community.feed(sort="recent")] == [new.id, old.id]


def test_top_feed_orders_by_score(db, user):
    quiet = _post(db, user, title="quiet")
    loud = _post(db, user, title="loud")
    community.apply_vote(user.id, loud.id, 1)

    entries = community.feed(sort="top")
    assert [e["post"].id for e in entries] == [loud.id, quiet.id]
    assert entries[0]["score"] == 1


def test_hot_feed_excludes_posts_older_than_the_window(db, user):
    stale = _post(db, user, title="stale",
                  created_at=datetime.utcnow() - timedelta(days=community.TRENDING_WINDOW_DAYS + 1))
    community.apply_vote(user.id, stale.id, 1)
    fresh = _post(db, user, title="fresh")

    assert [e["post"].id for e in community.feed(sort="hot")] == [fresh.id]


def test_feed_filters_by_category(db, user):
    analysis = _post(db, user, category=PostCategory.ANALYSIS)
    _post(db, user, category=PostCategory.QUESTION)

    entries = community.feed(category=PostCategory.ANALYSIS)
    assert [e["post"].id for e in entries] == [analysis.id]


def test_feed_filters_by_mentioned_asset(db, user):
    ry = _asset(db, "RY")
    _asset(db, "SU")
    about_ry = _post(db, user, body="Sigo con $RY")
    _post(db, user, body="Prefiero $SU")

    entries = community.feed(asset_id=ry.id)
    assert [e["post"].id for e in entries] == [about_ry.id]


def test_feed_hides_soft_deleted_posts(db, user):
    visible = _post(db, user, title="visible")
    removed = _post(db, user, title="removed")
    removed.is_deleted = True
    db.session.commit()

    assert [e["post"].id for e in community.feed()] == [visible.id]


def test_feed_counts_only_live_comments(db, user):
    post = _post(db, user)
    db.session.add(Comment(post_id=post.id, user_id=user.id, body="a", created_at=datetime.utcnow()))
    gone = Comment(post_id=post.id, user_id=user.id, body="b", created_at=datetime.utcnow(),
                   is_deleted=True)
    db.session.add(gone)
    db.session.commit()

    assert community.feed()[0]["comment_count"] == 1


# ── Trending sidebar ─────────────────────────────────────────────────────

def test_trending_ranks_by_mention_count_inside_the_window(db, user):
    _asset(db, "BCE")
    _asset(db, "SU")
    _post(db, user, body="$BCE preocupa")
    _post(db, user, body="$BCE otra vez")
    _post(db, user, body="$SU sube")

    ranking = community.trending_assets()
    assert [(r["asset"].symbol, r["mentions"]) for r in ranking] == [("BCE", 2), ("SU", 1)]


def test_trending_ignores_mentions_from_deleted_posts(db, user):
    _asset(db, "BCE")
    removed = _post(db, user, body="$BCE")
    removed.is_deleted = True
    db.session.commit()

    assert community.trending_assets() == []


# ── Rate limiting ────────────────────────────────────────────────────────

def test_rate_limit_trips_at_the_configured_count(db, user):
    for _ in range(community.POST_RATE_LIMIT - 1):
        _post(db, user)
    assert not community.rate_limited(
        user.id, Post, community.POST_RATE_LIMIT, community.POST_RATE_WINDOW
    )

    _post(db, user)
    assert community.rate_limited(
        user.id, Post, community.POST_RATE_LIMIT, community.POST_RATE_WINDOW
    )


def test_rate_limit_ignores_posts_outside_the_window(db, user):
    for _ in range(community.POST_RATE_LIMIT):
        _post(db, user, created_at=datetime.utcnow() - timedelta(hours=2))

    assert not community.rate_limited(
        user.id, Post, community.POST_RATE_LIMIT, community.POST_RATE_WINDOW
    )


def test_a_ticker_only_in_the_title_still_counts_as_a_mention(db, user):
    """A headline is as much a mention as the body — counting only the body
    would undercount the trending ranking."""
    _asset(db, "RY")
    post = _post(db, user, title="$RY sube el dividendo", body="Payout cómodo en 46%.")

    assert [m.asset.symbol for m in PostTickerMention.query.filter_by(post_id=post.id)] == ["RY"]


def test_the_title_is_not_linkified(db, user):
    """The title is already a link to the post, and anchors cannot nest."""
    _asset(db, "RY")
    html = str(community.render_body("Payout cómodo.", lambda a: f"/x/{a.symbol}"))

    assert "<a" not in html
