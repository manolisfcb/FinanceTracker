from src.extensions import db


class JobRun(db.Model):
    __tablename__ = 'job_runs'

    id = db.Column(db.Integer, primary_key=True)
    job = db.Column(db.String(50), nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='running')
    items_processed = db.Column(db.Integer, nullable=True)
    error = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<JobRun(job={self.job}, status={self.status}, started_at={self.started_at})>"

    def serialize(self):
        return {
            "id": self.id,
            "job": self.job,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "items_processed": self.items_processed,
            "error": self.error,
        }
