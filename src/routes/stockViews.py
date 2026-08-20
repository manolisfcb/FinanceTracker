import csv
import io
from urllib.parse import urlencode

from flask import Blueprint, Response, abort, jsonify, render_template, request
from flask_login import login_required
from sqlalchemy import and_, func, or_

from src.extensions import db
from src.forms.StockForm import Stock
from src.models import Asset, DividendHistory, Fundamentals
from src.services.market_data import get_provider

stocks_bp = Blueprint('stocks', __name__)

# (query key, column header) — drives both the table and the CSV export, in
# display order. 'symbol' renders as "Activo" (symbol + name stacked).
COLUMNS = [
    ('symbol', 'Activo'),
    ('exchange', 'Exchange'),
    ('sector', 'Sector'),
    ('price', 'Precio'),
    ('pe', 'P/E'),
    ('pb', 'P/B'),
    ('roe', 'ROE'),
    ('debt_to_equity', 'D/E'),
    ('dividend_yield', 'Div. yield'),
    ('payout_ratio', 'Payout'),
    ('net_margin', 'Margen neto'),
    ('market_cap', 'Mkt cap'),
]

SORTABLE_COLUMNS = {
    'symbol': Asset.symbol,
    'exchange': Asset.exchange,
    'sector': Asset.sector,
    'price': Fundamentals.price,
    'pe': Fundamentals.pe,
    'pb': Fundamentals.pb,
    'roe': Fundamentals.roe,
    'debt_to_equity': Fundamentals.debt_to_equity,
    'dividend_yield': Fundamentals.dividend_yield,
    'payout_ratio': Fundamentals.payout_ratio,
    'net_margin': Fundamentals.net_margin,
    'market_cap': Fundamentals.market_cap,
}

# Indicator keys filterable by <key>_min/<key>_max — also drives the range
# filter inputs rendered in the sidebar, so backend and UI can't drift apart.
RANGE_FILTER_LABELS = {
    'pe': 'P/E',
    'pb': 'P/B',
    'roe': 'ROE %',
    'debt_to_equity': 'D/E',
    'dividend_yield': 'Div. yield %',
    'payout_ratio': 'Payout %',
    'net_margin': 'Margen neto %',
    'market_cap': 'Mkt cap',
}

# Company page indicator grid: (Fundamentals column, label, format kind).
# 'percent' vs 'ratio' picks which Jinja filter the template applies —
# single source of truth so the grouping can't drift from what Fundamentals
# actually stores.
INDICATOR_GROUPS = [
    ('Valuación', [
        ('pe', 'P/E', 'ratio'),
        ('forward_pe', 'P/E forward', 'ratio'),
        ('pb', 'P/B', 'ratio'),
        ('ps', 'P/S', 'ratio'),
        ('ev_ebitda', 'EV/EBITDA', 'ratio'),
        ('market_cap', 'Market cap', 'compact_number'),
    ]),
    ('Rentabilidad', [
        ('roe', 'ROE', 'percent'),
        ('roa', 'ROA', 'percent'),
        ('gross_margin', 'Margen bruto', 'percent'),
        ('operating_margin', 'Margen operativo', 'percent'),
        ('net_margin', 'Margen neto', 'percent'),
    ]),
    ('Endeudamiento', [
        ('debt_to_equity', 'Deuda/Patrimonio', 'ratio'),
        ('current_ratio', 'Current ratio', 'ratio'),
        ('quick_ratio', 'Quick ratio', 'ratio'),
    ]),
    ('Dividendos', [
        ('dividend_yield', 'Div. yield', 'percent'),
        ('payout_ratio', 'Payout', 'percent'),
        ('dividend_rate', 'Div. rate/acción', 'ratio'),
    ]),
]

PRICE_HISTORY_RANGES = ('1M', '6M', '1Y', '5Y')


def _parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest_fundamentals_query():
    """Asset joined to its most recent Fundamentals snapshot (outer join, so
    assets with no snapshot yet still show up with null indicators)."""
    latest = (
        db.session.query(
            Fundamentals.asset_id.label('asset_id'),
            func.max(Fundamentals.as_of_date).label('max_date'),
        )
        .group_by(Fundamentals.asset_id)
        .subquery()
    )
    return (
        db.session.query(Asset, Fundamentals)
        .outerjoin(latest, Asset.id == latest.c.asset_id)
        .outerjoin(
            Fundamentals,
            and_(
                Fundamentals.asset_id == latest.c.asset_id,
                Fundamentals.as_of_date == latest.c.max_date,
            ),
        )
    )


def _apply_filters(query):
    search = request.args.get('q', '').strip()
    if search:
        query = query.filter(
            or_(Asset.symbol.ilike(f"%{search}%"), Asset.name.ilike(f"%{search}%"))
        )

    exchanges = request.args.getlist('exchange')
    if exchanges:
        query = query.filter(Asset.exchange.in_(exchanges))

    sectors = request.args.getlist('sector')
    if sectors:
        query = query.filter(Asset.sector.in_(sectors))

    for key in RANGE_FILTER_LABELS:
        column = SORTABLE_COLUMNS[key]
        min_value = _parse_float(request.args.get(f'{key}_min'))
        max_value = _parse_float(request.args.get(f'{key}_max'))
        if min_value is not None:
            query = query.filter(column >= min_value)
        if max_value is not None:
            query = query.filter(column <= max_value)

    return query


def _current_sort():
    sort = request.args.get('sort', 'market_cap')
    if sort not in SORTABLE_COLUMNS:
        sort = 'market_cap'
    direction = 'asc' if request.args.get('dir') == 'asc' else 'desc'
    return sort, direction


def _apply_sort(query, sort, direction):
    column = SORTABLE_COLUMNS[sort]
    return query.order_by(column.asc() if direction == 'asc' else column.desc())


def _sort_links(sort, direction):
    """Per-column header links that toggle sort/dir while preserving every
    other active filter, and reset pagination back to page 1."""
    args = request.args.to_dict(flat=False)
    args.pop('page', None)
    links = {}
    for key in SORTABLE_COLUMNS:
        next_dir = 'asc' if (sort == key and direction == 'desc') else 'desc'
        overridden = dict(args)
        overridden['sort'] = [key]
        overridden['dir'] = [next_dir]
        links[key] = urlencode(overridden, doseq=True)
    return links


@stocks_bp.route('/stocks', methods=['GET'])
@login_required
def get_stocks():
    page = request.args.get('page', 1, type=int)
    per_page = 25

    sort, direction = _current_sort()
    query = _apply_sort(_apply_filters(_latest_fundamentals_query()), sort, direction)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    exchanges = [
        row[0] for row in
        db.session.query(Asset.exchange).distinct().order_by(Asset.exchange).all()
    ]
    sectors = [
        row[0] for row in
        db.session.query(Asset.sector).filter(Asset.sector.isnot(None)).distinct().order_by(Asset.sector).all()
    ]

    context = {
        'rows': pagination.items,
        'pagination': pagination,
        'columns': COLUMNS,
        'exchanges': exchanges,
        'sectors': sectors,
        'range_filters': RANGE_FILTER_LABELS,
        'sort': sort,
        'dir': direction,
        'sort_links': _sort_links(sort, direction),
    }

    if request.headers.get('HX-Request'):
        return render_template('partials/screener_table.html', **context)
    return render_template('stocks/screener.html', **context)


@stocks_bp.route('/stocks/export.csv', methods=['GET'])
@login_required
def export_stocks_csv():
    sort, direction = _current_sort()
    query = _apply_sort(_apply_filters(_latest_fundamentals_query()), sort, direction)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([key for key, _ in COLUMNS] + ['name'])
    for asset, fundamentals in query.all():
        writer.writerow([
            asset.symbol,
            asset.exchange,
            asset.sector,
            getattr(fundamentals, 'price', None),
            getattr(fundamentals, 'pe', None),
            getattr(fundamentals, 'pb', None),
            getattr(fundamentals, 'roe', None),
            getattr(fundamentals, 'debt_to_equity', None),
            getattr(fundamentals, 'dividend_yield', None),
            getattr(fundamentals, 'payout_ratio', None),
            getattr(fundamentals, 'net_margin', None),
            getattr(fundamentals, 'market_cap', None),
            asset.name,
        ])

    return Response(
        buffer.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=screener.csv'},
    )


def _latest_fundamentals_for(asset_id):
    return (
        Fundamentals.query
        .filter_by(asset_id=asset_id)
        .order_by(Fundamentals.as_of_date.desc())
        .first()
    )


def _dividends_by_year(asset_id):
    """(year, total amount) pairs, oldest first — feeds the annual dividend
    bar chart. Grouped in Python rather than SQL: dividend currency can vary
    a symbol's history over time (rare, but real for interlisted stocks), so
    a naive SUM() would silently mix currencies."""
    records = (
        DividendHistory.query
        .filter_by(asset_id=asset_id)
        .order_by(DividendHistory.ex_date.asc())
        .all()
    )
    totals = {}
    for record in records:
        year = record.ex_date.year
        totals[year] = totals.get(year, 0.0) + record.amount
    return sorted(totals.items())


@stocks_bp.route('/stocks/<exchange>/<symbol>', methods=['GET'])
@login_required
def get_stock_detail(exchange, symbol):
    asset = Asset.query.filter_by(exchange=exchange, symbol=symbol).first()
    if asset is None:
        abort(404)

    fundamentals = _latest_fundamentals_for(asset.id)

    # Best-effort live quote for price + day change. Capped to a single,
    # non-throttled attempt (unlike the batch jobs) so a slow/rate-limited
    # Yahoo response can't stall the page — falls back to the latest stored
    # snapshot when it fails or returns nothing.
    quote = None
    try:
        quote = get_provider(max_retries=1, min_interval_seconds=0).get_quote(asset.yahoo_symbol)
    except Exception:
        quote = None

    price = (quote or {}).get('price')
    previous_close = (quote or {}).get('previous_close')
    if price is None and fundamentals:
        price = fundamentals.price
    change_amount = change_percent = None
    if price is not None and previous_close:
        change_amount = price - previous_close
        change_percent = (change_amount / previous_close) * 100

    dividends = (
        DividendHistory.query
        .filter_by(asset_id=asset.id)
        .order_by(DividendHistory.ex_date.desc())
        .limit(20)
        .all()
    )
    dividend_years, dividend_totals = zip(*_dividends_by_year(asset.id)) if dividends else ((), ())

    form = Stock()
    form.ticket.data = asset.symbol
    if price is not None:
        form.price.data = price

    context = {
        'asset': asset,
        'fundamentals': fundamentals,
        'price': price,
        'change_amount': change_amount,
        'change_percent': change_percent,
        'indicator_groups': INDICATOR_GROUPS,
        'price_ranges': PRICE_HISTORY_RANGES,
        'dividends': dividends,
        'dividend_years': list(dividend_years),
        'dividend_totals': list(dividend_totals),
        'form': form,
    }
    return render_template('stocks/company.html', **context)


@stocks_bp.route('/api/assets/search', methods=['GET'])
@login_required
def search_assets():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    assets = (
        Asset.query.filter(or_(Asset.symbol.ilike(f"%{query}%"), Asset.name.ilike(f"%{query}%")))
        .order_by(Asset.symbol.asc())
        .limit(20)
        .all()
    )
    return jsonify([{"symbol": a.symbol, "name": a.name, "exchange": a.exchange} for a in assets])


@stocks_bp.route('/api/assets/<int:asset_id>/prices', methods=['GET'])
@login_required
def get_asset_prices(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    range_key = request.args.get('range', '1Y').upper()
    if range_key not in PRICE_HISTORY_RANGES:
        range_key = '1Y'

    provider = get_provider()
    history = provider.get_price_history(asset.yahoo_symbol, range_key)
    return jsonify({
        'range': range_key,
        'dates': [point['date'] for point in history],
        'close': [point['close'] for point in history],
    })
