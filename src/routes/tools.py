from flask import Blueprint, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import and_, func

from src.extensions import db
from src.models import Asset, Fundamentals
from src.services.value_methods import METHODS, rank_companies


tools_bp = Blueprint("tools", __name__)


def _latest_fundamentals_rows():
    latest = (
        db.session.query(
            Fundamentals.asset_id.label("asset_id"),
            func.max(Fundamentals.as_of_date).label("max_date"),
        )
        .group_by(Fundamentals.asset_id)
        .subquery()
    )
    return (
        db.session.query(Asset, Fundamentals)
        .join(latest, Asset.id == latest.c.asset_id)
        .join(
            Fundamentals,
            and_(
                Fundamentals.asset_id == latest.c.asset_id,
                Fundamentals.as_of_date == latest.c.max_date,
            ),
        )
        .filter(
            Asset.is_active.is_(True),
            Asset.sector.isnot(None),
            ~Asset.sector.in_(("ETFs", "Cryptoassets")),
        )
        .all()
    )


@tools_bp.route("/tools/value-methods", methods=["GET"])
@login_required
def value_methods():
    method_slug = request.args.get("method", "graham")
    if method_slug not in METHODS:
        method_slug = "graham"
    selected_sector = request.args.get("sector", "").strip()
    selected_exchange = request.args.get("exchange", "").strip().upper()

    rows = _latest_fundamentals_rows()
    exchanges = sorted({asset.exchange for asset, _ in rows})
    if selected_exchange in exchanges:
        rows = [(asset, fundamentals) for asset, fundamentals in rows if asset.exchange == selected_exchange]
    else:
        selected_exchange = ""

    sector_groups = rank_companies(rows, method_slug)
    sectors = [group["sector"] for group in sector_groups]
    if selected_sector:
        sector_groups = [group for group in sector_groups if group["sector"] == selected_sector]
        if not sector_groups:
            selected_sector = ""
            sector_groups = rank_companies(rows, method_slug)

    eligible_count = sum(len(group["rows"]) for group in sector_groups)
    leaders = [group["rows"][0] for group in sector_groups if group["rows"]]
    last_update = max(
        (fundamentals.as_of_date for _, fundamentals in rows if fundamentals.as_of_date),
        default=None,
    )
    preserved_filters = {}
    if selected_sector:
        preserved_filters["sector"] = selected_sector
    if selected_exchange:
        preserved_filters["exchange"] = selected_exchange
    method_urls = {
        slug: url_for("tools.value_methods", method=slug, **preserved_filters)
        for slug in METHODS
    }

    return render_template(
        "tools/value_methods.html",
        methods=METHODS,
        active_method=METHODS[method_slug],
        method_slug=method_slug,
        sector_groups=sector_groups,
        sectors=sectors,
        selected_sector=selected_sector,
        exchanges=exchanges,
        selected_exchange=selected_exchange,
        leaders=leaders,
        eligible_count=eligible_count,
        last_update=last_update,
        method_urls=method_urls,
    )
