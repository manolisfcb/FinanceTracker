from flask import Blueprint, jsonify, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import and_, func

from src.extensions import db
from src.models import Asset, DividendHistory, Fundamentals
from src.services.comparator import build_comparison, normalize_price_history
from src.services.market_data import get_provider
from src.services.rankings import best_roe_by_sector, dividend_aristocrats, top_dividend_yield
from src.services.value_methods import METHODS, rank_companies


tools_bp = Blueprint("tools", __name__)


COMPARATOR_RANGES = ("1M", "6M", "1Y", "5Y")
COMPARATOR_COLORS = ("#b3372b", "#293b49", "#4f98a1", "#d27a5e")


def _latest_fundamentals_rows(equities_only=True, include_without_fundamentals=False):
    latest = (
        db.session.query(
            Fundamentals.asset_id.label("asset_id"),
            func.max(Fundamentals.as_of_date).label("max_date"),
        )
        .group_by(Fundamentals.asset_id)
        .subquery()
    )
    query = db.session.query(Asset, Fundamentals)
    join = query.outerjoin if include_without_fundamentals else query.join
    query = join(latest, Asset.id == latest.c.asset_id)
    join = query.outerjoin if include_without_fundamentals else query.join
    query = join(
        Fundamentals,
        and_(
            Fundamentals.asset_id == latest.c.asset_id,
            Fundamentals.as_of_date == latest.c.max_date,
        ),
    ).filter(Asset.is_active.is_(True))
    if equities_only:
        query = query.filter(
            Asset.sector.isnot(None),
            ~Asset.sector.in_(("ETFs", "Cryptoassets")),
        )
    return query.all()


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


@tools_bp.route("/tools/rankings", methods=["GET"])
@login_required
def rankings():
    rows = _latest_fundamentals_rows()
    assets = Asset.query.filter_by(is_active=True).all()
    asset_ids = [asset.id for asset in assets]
    dividends = (
        DividendHistory.query.filter(DividendHistory.asset_id.in_(asset_ids)).all()
        if asset_ids else []
    )
    latest_update = max(
        (fundamentals.as_of_date for _, fundamentals in rows if fundamentals.as_of_date),
        default=None,
    )
    return render_template(
        "tools/rankings.html",
        yield_ranking=top_dividend_yield(rows),
        aristocrats=dividend_aristocrats(assets, dividends),
        roe_groups=best_roe_by_sector(rows),
        latest_update=latest_update,
    )


def _selected_comparator_rows():
    requested_ids = []
    for asset_id in request.args.getlist("asset", type=int):
        if asset_id not in requested_ids:
            requested_ids.append(asset_id)
    requested_ids = requested_ids[:4]

    all_rows = _latest_fundamentals_rows(
        equities_only=False,
        include_without_fundamentals=True,
    )
    by_id = {asset.id: (asset, fundamentals) for asset, fundamentals in all_rows}
    return [by_id[asset_id] for asset_id in requested_ids if asset_id in by_id]


@tools_bp.route("/tools/comparator", methods=["GET"])
@login_required
def comparator():
    rows = _selected_comparator_rows()
    comparison = build_comparison(rows)
    selected_ids = [column["asset"].id for column in comparison["columns"]]
    remove_urls = {
        asset_id: url_for(
            "tools.comparator",
            **{"asset": [other for other in selected_ids if other != asset_id]},
        )
        for asset_id in selected_ids
    }
    return render_template(
        "tools/comparator.html",
        comparison=comparison,
        selected_ids=selected_ids,
        remove_urls=remove_urls,
        ranges=COMPARATOR_RANGES,
        colors=COMPARATOR_COLORS,
    )


@tools_bp.route("/api/tools/comparator/prices", methods=["GET"])
@login_required
def comparator_prices():
    asset_ids = []
    for asset_id in request.args.getlist("asset", type=int):
        if asset_id not in asset_ids:
            asset_ids.append(asset_id)
    asset_ids = asset_ids[:4]
    range_key = request.args.get("range", "5Y").upper()
    if range_key not in COMPARATOR_RANGES:
        range_key = "5Y"

    assets = Asset.query.filter(Asset.id.in_(asset_ids), Asset.is_active.is_(True)).all()
    by_id = {asset.id: asset for asset in assets}
    provider = get_provider(max_retries=1, min_interval_seconds=0)
    series = []
    for asset_id in asset_ids:
        asset = by_id.get(asset_id)
        if asset is None:
            continue
        try:
            history = provider.get_price_history(asset.yahoo_symbol, range_key)
        except Exception:
            history = []
        points = normalize_price_history(history)
        series.append({
            "asset_id": asset.id,
            "symbol": asset.symbol,
            "currency": asset.currency,
            "points": points,
            "ending_return": points[-1]["value"] if points else None,
        })

    return jsonify({"range": range_key, "series": series})
