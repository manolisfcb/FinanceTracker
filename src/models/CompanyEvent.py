import enum

from src.extensions import db


class CompanyEventKind(enum.Enum):
    FILING = "FILING"
    EARNINGS = "EARNINGS"
    DIVIDEND = "DIVIDEND"
    NEWS = "NEWS"


class CompanyEvent(db.Model):
    __tablename__ = 'company_events'
    __table_args__ = (
        db.UniqueConstraint('asset_id', 'source', 'external_id', name='uq_company_event_asset_source_external'),
    )

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    kind = db.Column(db.Enum(CompanyEventKind), nullable=False, index=True)
    source = db.Column(db.String(16), nullable=False)
    external_id = db.Column(db.String(64), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(512), nullable=True)
    published_at = db.Column(db.DateTime, nullable=False, index=True)
    # When the event itself happens, for events announced ahead of time (a
    # dividend's ex-date, the next earnings date). `published_at` orders the
    # inbox timeline; `event_date` orders the upcoming-dividends calendar.
    event_date = db.Column(db.Date, nullable=True)

    asset = db.relationship('Asset', backref='company_events', lazy=True)

    def __repr__(self):
        return f"<CompanyEvent(asset_id={self.asset_id}, kind={self.kind}, published_at={self.published_at})>"

    def serialize(self):
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "kind": self.kind.value,
            "source": self.source,
            "external_id": self.external_id,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "published_at": self.published_at,
            "event_date": self.event_date,
        }


class CompanyEventRead(db.Model):
    """Presence of a row means the user has read that event."""

    __tablename__ = 'company_event_reads'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'company_event_id', name='uq_company_event_read_user_event'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    company_event_id = db.Column(db.Integer, db.ForeignKey('company_events.id'), nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f"<CompanyEventRead(user_id={self.user_id}, company_event_id={self.company_event_id})>"
