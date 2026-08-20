import enum

from src.extensions import db


class PostCategory(enum.Enum):
    """Sections of the community feed.

    There is deliberately no `FEED` member: "Feed" in the UI is the
    *no-filter* view, not a category a post can be filed under.
    """

    ANALYSIS = "ANALYSIS"
    QUESTION = "QUESTION"
    DIVIDENDS = "DIVIDENDS"
    NEWS = "NEWS"
    TRADES = "TRADES"
    SUGGESTIONS = "SUGGESTIONS"


POST_CATEGORY_LABELS = {
    PostCategory.ANALYSIS: "Análisis",
    PostCategory.QUESTION: "Dudas",
    PostCategory.DIVIDENDS: "Dividendos",
    PostCategory.NEWS: "Noticias",
    PostCategory.TRADES: "Operaciones",
    PostCategory.SUGGESTIONS: "Sugerencias",
}

# Tailwind background/text pairs, mirroring the palette of the mockup so a
# category is recognisable by colour before the label is read.
POST_CATEGORY_STYLES = {
    PostCategory.ANALYSIS: "bg-[#e9efe9] text-[#1a7f4e]",
    PostCategory.QUESTION: "bg-[#eceef2] text-[#4a6b8a]",
    PostCategory.DIVIDENDS: "bg-[#f0eae9] text-[#b3372b]",
    PostCategory.NEWS: "bg-[#eae9ef] text-[#7d5ba6]",
    PostCategory.TRADES: "bg-[#f3ece3] text-[#b98a2e]",
    PostCategory.SUGGESTIONS: "bg-[#e8eeef] text-[#3f7f88]",
}


class Post(db.Model):
    __tablename__ = 'community_posts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    category = db.Column(db.Enum(PostCategory), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    # Moderation is soft: a removed post keeps its row so its comments, votes
    # and mention counts stay referentially intact and the removal is
    # auditable. Every read path filters on this.
    is_deleted = db.Column(db.Boolean, nullable=False, default=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    author = db.relationship('UserModel', foreign_keys=[user_id], lazy='joined')

    def __repr__(self):
        return f"<Post(id={self.id}, user_id={self.user_id}, category={self.category})>"

    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "body": self.body,
            "category": self.category.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_deleted": self.is_deleted,
        }


class Comment(db.Model):
    __tablename__ = 'community_comments'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    author = db.relationship('UserModel', foreign_keys=[user_id], lazy='joined')
    post = db.relationship('Post', backref=db.backref('comments', lazy=True))

    def __repr__(self):
        return f"<Comment(id={self.id}, post_id={self.post_id})>"


class Vote(db.Model):
    """One row per (user, post); `value` flips between +1 and -1.

    Withdrawing a vote deletes the row rather than storing a 0, so the score
    is a plain SUM and "has this user voted?" is a plain existence check.
    """

    __tablename__ = 'community_votes'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='uq_community_vote_user_post'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False, index=True)
    value = db.Column(db.SmallInteger, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f"<Vote(user_id={self.user_id}, post_id={self.post_id}, value={self.value})>"


class PostTickerMention(db.Model):
    """A `$TICKER` in a post body, resolved to an asset at write time.

    Denormalised out of the body so the company feed and the trending ranking
    are index lookups instead of a full-text scan, and so a mention that
    resolved to nothing simply produces no row.
    """

    __tablename__ = 'community_post_mentions'
    __table_args__ = (
        db.UniqueConstraint('post_id', 'asset_id', name='uq_community_mention_post_asset'),
    )

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, index=True)

    asset = db.relationship('Asset', lazy='joined')
    post = db.relationship('Post', backref=db.backref('mentions', lazy='joined'))

    def __repr__(self):
        return f"<PostTickerMention(post_id={self.post_id}, asset_id={self.asset_id})>"


class PostReport(db.Model):
    __tablename__ = 'community_post_reports'
    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='uq_community_report_post_user'),
    )

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f"<PostReport(post_id={self.post_id}, user_id={self.user_id})>"
