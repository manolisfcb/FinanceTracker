from datetime import datetime

import requests

from src.extensions import db, scheduler
from src.models import FxRate
from src.resources.jobs._common import run_job

VALET_URL = "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=1"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TrueNorthAnalytics/1.0)"}


def _refresh_usdcad():
    resp = requests.get(VALET_URL, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    observations = resp.json().get("observations", [])

    items = 0
    for obs in observations:
        obs_date = datetime.strptime(obs["d"], "%Y-%m-%d").date()
        rate_value = float(obs["FXUSDCAD"]["v"])
        row = FxRate.query.filter_by(date=obs_date).first()
        if row is None:
            row = FxRate(date=obs_date, pair="USDCAD")
            db.session.add(row)
        row.rate = rate_value
        items += 1
    return items


@scheduler.task('cron', id='refresh_fx', hour=18, minute=30, timezone='America/Toronto')
def refresh_fx():
    """Daily USD/CAD rate from the Bank of Canada Valet API."""
    with scheduler.app.app_context():
        run_job('refresh_fx', _refresh_usdcad)
