import csv
import io
from urllib.parse import quote_plus, urlencode

from flask import Blueprint, Response, abort, jsonify, render_template, request
from flask_login import login_required
from sqlalchemy import and_, func, or_

from src.extensions import db
from src.forms.StockForm import Stock
from src.models import Asset, CompanyEvent, CompanyEventKind, DividendHistory, Fundamentals
from src.services.company_data import backfill_asset, needs_backfill
from src.services.fundamentals import ensure_statement_metrics
from src.services.market_data import get_provider

stocks_bp = Blueprint('stocks', __name__)

# SEDAR+ has no public API, so Canadian filings are a search link, not data.
SEDAR_SEARCH_URL = "https://www.sedarplus.ca/csa-party/records/searchIssuer.html?keyword={query}"

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

# Company page indicator grid: (Fundamentals column, label, format kind, help).
#
# `kind` picks which Jinja filter the template applies ('percent' for 0-1
# fractions, 'compact_number' for absolute amounts, 'ratio' otherwise), and
# `help` is the text behind the "?" next to each label. Single source of
# truth, so the grouping, the formatting and the explanation can't drift from
# what Fundamentals actually stores. '{span}' is replaced at render time with
# the number of fiscal years the CAGR really covers.
INDICATOR_GROUPS = [
    ('Valuación', [
        ('pe', 'P/L (P/E)', 'ratio',
         'Precio sobre lucro: cuántas veces el precio de la acción contiene la ganancia '
         'por acción de los últimos 12 meses. Un P/L de 15 significa que, al ritmo de '
         'ganancias actual, harían falta 15 años para recuperar lo que pagás hoy. Más bajo '
         'suele ser más barato, pero también puede avisar que el mercado espera que esas '
         'ganancias caigan.'),
        ('forward_pe', 'P/L proyectado', 'ratio',
         'El mismo cálculo, pero contra la ganancia por acción que los analistas estiman '
         'para el próximo ejercicio en lugar de la ya reportada.'),
        ('pb', 'P/VP (P/B)', 'ratio',
         'Precio sobre valor patrimonial: cuántas veces el precio de mercado supera al '
         'patrimonio neto contable por acción. Por debajo de 1 la empresa cotiza por menos '
         'de lo que dicen sus libros.'),
        ('ps', 'PSR (P/Ventas)', 'ratio',
         'Precio sobre los ingresos anuales. Útil para comparar empresas que todavía no dan '
         'ganancias, donde el P/L directamente no existe.'),
        ('p_ebit', 'P/EBIT', 'ratio',
         'Capitalización de mercado sobre la ganancia operativa (antes de intereses e '
         'impuestos). Aísla el desempeño del negocio de cómo está financiado y de la carga '
         'impositiva.'),
        ('price_to_assets', 'P/Activos', 'ratio',
         'Capitalización de mercado sobre el activo total. Se usa sobre todo en bancos y '
         'aseguradoras, donde el balance es el negocio.'),
        ('ev_ebitda', 'EV/EBITDA', 'ratio',
         'Valor de la firma (capitalización + deuda − caja) sobre el EBITDA. Al incluir la '
         'deuda, compara mejor que el P/L a empresas con endeudamientos muy distintos.'),
        ('ev_ebit', 'EV/EBIT', 'ratio',
         'Igual que el EV/EBITDA pero contra la ganancia operativa, que sí descuenta '
         'depreciación y amortización. Más exigente en negocios intensivos en capital.'),
        ('book_value_per_share', 'VPA', 'ratio',
         'Valor patrimonial por acción: el patrimonio neto contable dividido por la cantidad '
         'de acciones. Es el denominador del P/VP.'),
        ('eps', 'LPA (BPA)', 'ratio',
         'Lucro por acción de los últimos 12 meses: la ganancia neta dividida por la cantidad '
         'de acciones. Es el denominador del P/L.'),
        ('market_cap', 'Capitalización', 'compact_number',
         'Valor de mercado de toda la empresa: precio de la acción por la cantidad de '
         'acciones en circulación.'),
    ]),
    ('Rentabilidad', [
        ('roe', 'ROE', 'percent',
         'Retorno sobre el patrimonio: cuánto gana la empresa por cada dólar aportado por '
         'los accionistas. Es la medida más directa de qué tan bien usa el capital propio.'),
        ('roa', 'ROA', 'percent',
         'Retorno sobre los activos: cuánto gana por cada dólar de activo, sin importar si '
         'ese activo se financió con deuda o con capital propio.'),
        ('roic', 'ROIC', 'percent',
         'Retorno sobre el capital invertido: ganancia operativa después de impuestos sobre '
         'patrimonio más deuda bruta. Comparado con el costo de ese capital, dice si la '
         'empresa crea o destruye valor. Calculado acá a partir del balance, porque Yahoo no '
         'lo publica.'),
        ('gross_margin', 'Margen bruto', 'percent',
         'Qué porcentaje de los ingresos sobrevive al costo directo de lo vendido. Habla del '
         'poder de la empresa para fijar precios.'),
        ('operating_margin', 'Margen EBIT', 'percent',
         'Qué porcentaje de los ingresos queda como ganancia operativa, ya descontados todos '
         'los gastos de la operación.'),
        ('ebitda_margin', 'Margen EBITDA', 'percent',
         'Igual que el margen EBIT pero sumando de nuevo depreciación y amortización, que no '
         'son salidas de caja. Se acerca a lo que la operación genera en efectivo.'),
        ('net_margin', 'Margen neto', 'percent',
         'Qué porcentaje de los ingresos termina como ganancia final, ya pagados intereses e '
         'impuestos.'),
    ]),
    ('Endeudamiento', [
        ('total_debt', 'Deuda bruta', 'compact_number',
         'Todo lo que la empresa debe a bancos y tenedores de bonos, de corto y de largo '
         'plazo, sin descontar la caja.'),
        ('net_debt', 'Deuda neta', 'compact_number',
         'Deuda bruta menos la caja e inversiones líquidas. En negativo significa que la '
         'empresa tiene más caja que deuda.'),
        ('net_debt_to_equity', 'Deuda neta/Patrimonio', 'ratio',
         'Cuántas veces la deuda neta supera al patrimonio de los accionistas. Cuanto más '
         'alto, más apalancada está la empresa y más sensible a una suba de tasas.'),
        ('net_debt_to_ebitda', 'Deuda neta/EBITDA', 'ratio',
         'Cuántos años de EBITDA harían falta para cancelar la deuda neta. Arriba de 3 suele '
         'considerarse exigente, aunque el umbral depende del sector.'),
        ('debt_to_equity', 'Deuda/Patrimonio', 'ratio',
         'Deuda bruta sobre patrimonio, tal como la publica Yahoo: en puntos porcentuales, '
         'así que 158,40 equivale a 1,58 veces el patrimonio.'),
        ('liabilities_to_assets', 'Pasivo/Activos', 'ratio',
         'Qué proporción del activo total está financiada por terceros y no por los '
         'accionistas.'),
        ('current_ratio', 'Liquidez corriente', 'ratio',
         'Activo corriente sobre pasivo corriente: si lo que cobra en los próximos doce meses '
         'alcanza para cubrir lo que tiene que pagar. Debajo de 1 hay tensión de caja.'),
        ('quick_ratio', 'Liquidez seca', 'ratio',
         'Lo mismo, pero sin contar los inventarios, que son lo más lento de convertir en '
         'efectivo.'),
    ]),
    ('Eficiencia y crecimiento', [
        ('asset_turnover', 'Giro del activo', 'ratio',
         'Cuántos dólares de ingresos genera por cada dólar de activo. Alto en comercio '
         'minorista, bajo en infraestructura: sólo compara bien dentro del mismo sector.'),
        ('revenue_cagr', 'CAGR ingresos ({span})', 'percent',
         'Crecimiento anual compuesto de los ingresos a lo largo de los últimos {span} de '
         'estados contables disponibles. Suaviza los años buenos y malos en una sola tasa.'),
        ('revenue_growth_5y', 'Crecimiento ingresos (a/a)', 'percent',
         'Variación de los ingresos contra el mismo período del año anterior, según Yahoo.'),
        ('eps_growth_5y', 'Crecimiento LPA (a/a)', 'percent',
         'Variación de la ganancia por acción contra el mismo período del año anterior.'),
        ('beta', 'Beta', 'ratio',
         'Cuánto se mueve la acción frente al mercado. Beta 1 acompaña al índice; arriba de 1 '
         'amplifica sus subas y sus bajas; debajo de 1 las amortigua.'),
    ]),
    ('Dividendos', [
        ('dividend_yield', 'Dividend yield', 'percent',
         'Dividendos de los últimos 12 meses sobre el precio actual: el retorno en efectivo '
         'que paga la acción a este precio.'),
        ('payout_ratio', 'Payout', 'percent',
         'Qué porcentaje de la ganancia se reparte como dividendo. Sostenidamente arriba de '
         '100% significa que la empresa paga más de lo que gana.'),
        ('dividend_rate', 'Dividendo por acción', 'ratio',
         'Monto anual estimado que paga cada acción, en la moneda del activo.'),
    ]),
]

PRICE_HISTORY_RANGES = ('1M', '6M', '1Y', '5Y')

# Span assumed for the revenue CAGR label when no statements were parsed.
DEFAULT_CAGR_YEARS = 5


def _indicator_groups_for(fundamentals):
    """INDICATOR_GROUPS with '{span}' resolved to the number of fiscal years
    the revenue CAGR actually covers — free Yahoo statements carry four
    usable years for most companies, so a hardcoded "5A" in the label would
    misstate what was measured. Abbreviated in the label, spelled out in the
    explanation behind the "?"."""
    years = getattr(fundamentals, 'revenue_cagr_years', None) or DEFAULT_CAGR_YEARS
    return [
        (group_name, [
            (
                key,
                label.replace('{span}', f"{int(years)}A"),
                kind,
                help_text.replace('{span}', f"{int(years)} años"),
            )
            for key, label, kind, help_text in rows
        ])
        for group_name, rows in INDICATOR_GROUPS
    ]


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

    # The nightly jobs only sweep assets someone holds, so the rest of the
    # universe would show empty dividends/filings/news forever. Fill this one
    # in on first view instead of fetching all ~1100 every night.
    if needs_backfill(asset):
        backfill_asset(asset)

    # Statement-derived indicators (P/EBIT, ROIC, deuda neta/EBITDA, giro del
    # activo) aren't part of the nightly sweep — they're filled here, on the
    # page that shows them. See src/services/fundamentals.py.
    fundamentals = ensure_statement_metrics(asset, _latest_fundamentals_for(asset.id))

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

    next_earnings = (
        CompanyEvent.query
        .filter_by(asset_id=asset.id, kind=CompanyEventKind.EARNINGS)
        .first()
    )
    filings = (
        CompanyEvent.query
        .filter_by(asset_id=asset.id, kind=CompanyEventKind.FILING)
        .order_by(CompanyEvent.published_at.desc())
        .limit(10)
        .all()
    )
    news = (
        CompanyEvent.query
        .filter_by(asset_id=asset.id, kind=CompanyEventKind.NEWS)
        .order_by(CompanyEvent.published_at.desc())
        .limit(12)
        .all()
    )

    context = {
        'asset': asset,
        'fundamentals': fundamentals,
        'price': price,
        'change_amount': change_amount,
        'change_percent': change_percent,
        'indicator_groups': _indicator_groups_for(fundamentals),
        'price_ranges': PRICE_HISTORY_RANGES,
        'dividends': dividends,
        'dividend_years': list(dividend_years),
        'dividend_totals': list(dividend_totals),
        'next_earnings': next_earnings,
        'filings': filings,
        'news': news,
        'sedar_search_url': SEDAR_SEARCH_URL.format(query=quote_plus(asset.name)),
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
