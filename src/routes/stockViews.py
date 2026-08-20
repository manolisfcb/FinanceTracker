import csv
import io
from urllib.parse import quote_plus, urlencode

from flask import Blueprint, Response, abort, jsonify, make_response, render_template, request
from flask_login import login_required
from sqlalchemy import and_, func, or_

from src.extensions import db
from src.forms.StockForm import Stock
from src.models import Asset, CompanyEvent, CompanyEventKind, DividendHistory, Fundamentals
from src.services.company_data import backfill_asset, needs_backfill
from src.services.fundamentals import ensure_statement_metrics
from src.services.insights import build_company_insight
from src.services.market_data import get_provider

stocks_bp = Blueprint('stocks', __name__)

# SEDAR+ has no public API, so Canadian filings are a search link, not data.
SEDAR_SEARCH_URL = "https://www.sedarplus.ca/csa-party/records/searchIssuer.html?keyword={query}"

# (query key, column header) — the screener table in display order. 'symbol'
# renders as "Activo": symbol, exchange tag and company name stacked in one
# cell, so exchange gets no column of its own here. The CSV still carries it.
COLUMNS = [
    ('symbol', 'Activo'),
    ('sector', 'Sector'),
    ('price', 'Precio'),
    ('pe', 'P/E'),
    ('pb', 'P/B'),
    ('roe', 'ROE'),
    ('debt_to_equity', 'D/E'),
    ('net_margin', 'Margen neto'),
    ('dividend_yield', 'Div. yield'),
    ('payout_ratio', 'Payout'),
    ('market_cap', 'Mkt cap'),
]

# Every field the export writes, in order. Kept apart from COLUMNS because
# the table folds exchange and name into a single "Activo" cell and a CSV
# has no reason to.
EXPORT_FIELDS = [
    'symbol', 'name', 'exchange', 'sector', 'price', 'pe', 'pb', 'roe',
    'debt_to_equity', 'net_margin', 'dividend_yield', 'payout_ratio', 'market_cap',
]
ASSET_FIELDS = frozenset({'symbol', 'name', 'exchange', 'sector'})

# The two layouts of the same result set.
VIEWS = ('list', 'cards')

# 24 rather than 25: the cards layout is a three-column grid, and a page that
# doesn't divide by three ends on a ragged row.
PER_PAGE = 24

# ROE at or above this reads as green in the table and the cards; below it
# stays neutral. Payout turns red once the company pays out more than it earns.
ROE_STRONG = 0.10
PAYOUT_OVERPAYING = 1.0

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

# Indicator keys filterable by <key>_min/<key>_max, and the presets each one
# offers in its toolbar dropdown, as (label, min, max).
#
# The bounds are in the units the column is stored in — yields, margins and
# payout are 0-1 fractions, D/E comes from Yahoo in percentage points — so
# only the label is human-facing. Presets rather than free-text boxes because
# that is what the design's toolbar is, and because a "Div. yield" box that
# wants "0.03" for 3% gets filled in wrong every time.
FILTER_PRESETS = {
    'pe': ('P/E', [
        ('cualquiera', None, None),
        ('< 10', None, 10),
        ('< 15', None, 15),
        ('< 20', None, 20),
        ('< 25', None, 25),
        ('> 25', 25, None),
    ]),
    'dividend_yield': ('Div. yield', [
        ('cualquiera', None, None),
        ('> 1%', 0.01, None),
        ('> 2%', 0.02, None),
        ('> 3%', 0.03, None),
        ('> 5%', 0.05, None),
        ('> 7%', 0.07, None),
    ]),
    'roe': ('ROE', [
        ('cualquiera', None, None),
        ('> 5%', 0.05, None),
        ('> 10%', 0.10, None),
        ('> 15%', 0.15, None),
        ('> 20%', 0.20, None),
    ]),
    'pb': ('P/B', [
        ('cualquiera', None, None),
        ('< 1', None, 1),
        ('< 2', None, 2),
        ('< 3', None, 3),
        ('< 5', None, 5),
    ]),
    'debt_to_equity': ('D/E', [
        ('cualquiera', None, None),
        ('< 50', None, 50),
        ('< 100', None, 100),
        ('< 200', None, 200),
    ]),
    'net_margin': ('Margen neto', [
        ('cualquiera', None, None),
        ('> 5%', 0.05, None),
        ('> 10%', 0.10, None),
        ('> 20%', 0.20, None),
    ]),
    'payout_ratio': ('Payout', [
        ('cualquiera', None, None),
        ('< 40%', None, 0.40),
        ('< 60%', None, 0.60),
        ('< 80%', None, 0.80),
        ('< 100%', None, 1.0),
    ]),
    'market_cap': ('Mkt cap', [
        ('cualquiera', None, None),
        ('> 1B', 1e9, None),
        ('> 10B', 1e10, None),
        ('> 100B', 1e11, None),
    ]),
}

# Sector plus these three sit permanently in the toolbar, as in the design;
# the rest are added one at a time from "+ Agregar filtro".
PRIMARY_FILTERS = ('pe', 'dividend_yield', 'roe')
EXTRA_FILTERS = ('pb', 'debt_to_equity', 'net_margin', 'payout_ratio', 'market_cap')

# Company page indicator tiles: (Fundamentals column, label, format kind, help).
#
# `kind` picks which Jinja filter the template applies ('percent' for 0-1
# fractions, 'compact_number' for absolute amounts, 'ratio' otherwise), and
# `help` is the text behind the "?" on each tile. Single source of truth, so
# the grouping, the formatting and the explanation can't drift from what
# Fundamentals actually stores. '{span}' is replaced at render time with the
# number of fiscal years the CAGR really covers.
#
# Labels are abbreviated to fit a tile: the explanation carries the full name,
# which is the point of having one on every indicator. Market cap, LPA and
# beta live in the "Datos clave" card instead of here, so they aren't
# duplicated on the same screen.
INDICATOR_GROUPS = [
    ('Valuación', [
        ('pe', 'P/L', 'ratio',
         'Precio sobre lucro (P/E): cuántas veces el precio de la acción contiene la ganancia '
         'por acción de los últimos 12 meses. Un P/L de 15 significa que, al ritmo de '
         'ganancias actual, harían falta 15 años para recuperar lo que pagás hoy. Más bajo '
         'suele ser más barato, pero también puede avisar que el mercado espera que esas '
         'ganancias caigan.'),
        ('forward_pe', 'P/L fwd', 'ratio',
         'Precio sobre lucro proyectado: el mismo cálculo, pero contra la ganancia por acción '
         'que los analistas estiman para el próximo ejercicio en lugar de la ya reportada.'),
        ('pb', 'P/VP', 'ratio',
         'Precio sobre valor patrimonial (P/B): cuántas veces el precio de mercado supera al '
         'patrimonio neto contable por acción. Por debajo de 1 la empresa cotiza por menos de '
         'lo que dicen sus libros.'),
        ('ps', 'PSR', 'ratio',
         'Precio sobre ventas: el valor de mercado contra los ingresos anuales. Útil para '
         'comparar empresas que todavía no dan ganancias, donde el P/L directamente no existe.'),
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
    ]),
    ('Rentabilidad', [
        ('roe', 'ROE', 'percent',
         'Retorno sobre el patrimonio: cuánto gana la empresa por cada dólar aportado por los '
         'accionistas. Es la medida más directa de qué tan bien usa el capital propio.'),
        ('roa', 'ROA', 'percent',
         'Retorno sobre los activos: cuánto gana por cada dólar de activo, sin importar si ese '
         'activo se financió con deuda o con capital propio.'),
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
    ('Solidez', [
        ('total_debt', 'Deuda bruta', 'compact_number',
         'Todo lo que la empresa debe a bancos y tenedores de bonos, de corto y de largo '
         'plazo, sin descontar la caja.'),
        ('net_debt', 'Deuda neta', 'compact_number',
         'Deuda bruta menos la caja e inversiones líquidas. En negativo significa que la '
         'empresa tiene más caja que deuda.'),
        ('net_debt_to_equity', 'D. neta/Patr.', 'ratio',
         'Deuda neta sobre patrimonio: cuántas veces la deuda neta supera lo aportado por los '
         'accionistas. Cuanto más alto, más apalancada está la empresa y más sensible a una '
         'suba de tasas.'),
        ('net_debt_to_ebitda', 'D. neta/EBITDA', 'ratio',
         'Cuántos años de EBITDA harían falta para cancelar la deuda neta. Arriba de 3 suele '
         'considerarse exigente, aunque el umbral depende del sector.'),
        ('debt_to_equity', 'Deuda/Patr.', 'ratio',
         'Deuda bruta sobre patrimonio, tal como la publica Yahoo: en puntos porcentuales, '
         'así que 158,40 equivale a 1,58 veces el patrimonio.'),
        ('liabilities_to_assets', 'Pasivo/Activos', 'ratio',
         'Qué proporción del activo total está financiada por terceros y no por los '
         'accionistas.'),
        ('current_ratio', 'Liquidez corr.', 'ratio',
         'Liquidez corriente: activo corriente sobre pasivo corriente, o sea si lo que cobra '
         'en los próximos doce meses alcanza para cubrir lo que tiene que pagar. Debajo de 1 '
         'hay tensión de caja.'),
        ('quick_ratio', 'Liquidez seca', 'ratio',
         'Lo mismo que la liquidez corriente, pero sin contar los inventarios, que son lo más '
         'lento de convertir en efectivo.'),
    ]),
    ('Crecimiento', [
        ('revenue_cagr', 'CAGR ing. {span}', 'percent',
         'Crecimiento anual compuesto de los ingresos a lo largo de los últimos {span} de '
         'estados contables disponibles. Suaviza los años buenos y malos en una sola tasa.'),
        ('revenue_growth_5y', 'Ingresos a/a', 'percent',
         'Variación de los ingresos contra el mismo período del año anterior, según Yahoo.'),
        ('eps_growth_5y', 'LPA a/a', 'percent',
         'Variación de la ganancia por acción contra el mismo período del año anterior.'),
        ('asset_turnover', 'Giro del activo', 'ratio',
         'Cuántos dólares de ingresos genera por cada dólar de activo. Alto en comercio '
         'minorista, bajo en infraestructura: sólo compara bien dentro del mismo sector.'),
    ]),
    ('Dividendos', [
        ('dividend_yield', 'Yield', 'percent',
         'Dividend yield: dividendos de los últimos 12 meses sobre el precio actual, o sea el '
         'retorno en efectivo que paga la acción a este precio.'),
        ('payout_ratio', 'Payout', 'percent',
         'Qué porcentaje de la ganancia se reparte como dividendo. Sostenidamente arriba de '
         '100% significa que la empresa paga más de lo que gana.'),
        ('dividend_rate', 'Div./acción', 'ratio',
         'Monto anual estimado que paga cada acción, en la moneda del activo.'),
    ]),
]

# Explanations for the indicators that live in the "Datos clave" card next to
# the price chart rather than in a tile group.
KEY_STAT_HELP = {
    'market_cap':
        'Valor de mercado de toda la empresa: precio de la acción por la cantidad de acciones '
        'en circulación.',
    'fifty_two_week_range':
        'El precio más bajo y el más alto de las últimas 52 semanas. Ubica el precio de hoy '
        'dentro del rango en que se movió el último año.',
    'average_volume':
        'Cuántas acciones se negocian en un día promedio. Un volumen bajo hace más difícil '
        'entrar o salir sin mover el precio.',
    'beta':
        'Cuánto se mueve la acción frente al mercado. Beta 1 acompaña al índice; arriba de 1 '
        'amplifica sus subas y sus bajas; debajo de 1 las amortigua.',
    'eps':
        'Lucro por acción (LPA) de los últimos 12 meses: la ganancia neta dividida por la '
        'cantidad de acciones. Es el denominador del P/L.',
}

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

    for key in FILTER_PRESETS:
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


def _url_with(**overrides):
    """This request's URL with `overrides` applied: None drops a key, a list
    sets it to those values (empty list drops it too), anything else replaces
    it. Pagination always resets, since every override changes what page 1
    even means."""
    args = request.args.to_dict(flat=False)
    args.pop('page', None)
    for key, value in overrides.items():
        if value is None or (isinstance(value, (list, tuple)) and not value):
            args.pop(key, None)
        elif isinstance(value, (list, tuple)):
            args[key] = list(value)
        else:
            args[key] = [value]
    query = urlencode(args, doseq=True)
    return f"{request.path}?{query}" if query else request.path


def _sort_links(sort, direction):
    """Per-column header links that toggle sort/dir while preserving every
    other active filter, and reset pagination back to page 1."""
    links = {}
    for key in SORTABLE_COLUMNS:
        next_dir = 'asc' if (sort == key and direction == 'desc') else 'desc'
        links[key] = _url_with(sort=key, dir=next_dir)
    return links


def _bound(value):
    """A preset bound as it appears in the query string. Plain decimal rather
    than repr(), so 1e9 round-trips as '1000000000' and the link a preset
    builds is the same string we later compare against to find it selected."""
    if value is None:
        return None
    return f"{value:.10f}".rstrip('0').rstrip('.') or '0'


def _range_dropdown(key, open_extras):
    """One toolbar dropdown: its current label, its preset options, and — for
    the filters added from "+ Agregar filtro" — the link that takes it back
    out of the toolbar."""
    title, presets = FILTER_PRESETS[key]
    current_min = request.args.get(f'{key}_min') or None
    current_max = request.args.get(f'{key}_max') or None

    options = []
    label = None
    for preset_label, min_value, max_value in presets:
        as_min, as_max = _bound(min_value), _bound(max_value)
        active = (current_min == as_min and current_max == as_max)
        if active:
            label = preset_label
        options.append({
            'label': preset_label,
            'active': active,
            'url': _url_with(**{f'{key}_min': as_min, f'{key}_max': as_max}),
        })

    if label is None:
        # A hand-edited URL: no preset matches, so describe the bounds.
        if current_min and current_max:
            label = f"{current_min}–{current_max}"
        elif current_min:
            label = f"> {current_min}"
        else:
            label = f"< {current_max}"

    remove_url = None
    if key in EXTRA_FILTERS:
        remove_url = _url_with(**{
            f'{key}_min': None,
            f'{key}_max': None,
            'add': [extra for extra in open_extras if extra != key],
        })

    return {
        'key': key,
        'title': title,
        'label': label,
        'options': options,
        'remove_url': remove_url,
        'is_set': bool(current_min or current_max),
    }


def _sector_dropdown(sectors):
    """Sector filter. Multi-select, so each option toggles its own sector in
    and out of the current selection and the label collapses to a count once
    more than one is on."""
    selected = request.args.getlist('sector')
    options = [{
        'label': 'Todos',
        'active': not selected,
        'url': _url_with(sector=None),
    }]
    for sector in sectors:
        if sector in selected:
            toggled = [chosen for chosen in selected if chosen != sector]
        else:
            toggled = selected + [sector]
        options.append({
            'label': sector,
            'active': sector in selected,
            'url': _url_with(sector=toggled),
        })

    if not selected:
        label = 'Todos'
    elif len(selected) == 1:
        label = selected[0]
    else:
        label = f"{len(selected)} sectores"

    return {
        'key': 'sector',
        'title': 'Sector',
        'label': label,
        'options': options,
        'remove_url': None,
        'is_set': bool(selected),
    }


def _exchange_chips(exchanges):
    """Exchange chips. No `exchange` param means the whole universe, so every
    chip starts lit and clicking one turns that market off; turning the last
    one off lands back on the unfiltered set rather than on nothing."""
    selected = request.args.getlist('exchange')
    active = set(selected) if selected else set(exchanges)

    chips = []
    for exchange in exchanges:
        toggled = active - {exchange} if exchange in active else active | {exchange}
        if toggled == set(exchanges):
            toggled = set()
        chips.append({
            'label': exchange,
            'active': exchange in active,
            'url': _url_with(exchange=sorted(toggled)),
        })
    return chips


def _toolbar_filters(sectors):
    """The dropdowns the toolbar shows, left to right, plus what is still
    available behind "+ Agregar filtro"."""
    open_extras = [key for key in request.args.getlist('add') if key in EXTRA_FILTERS]
    shown_extras = [
        key for key in EXTRA_FILTERS
        if key in open_extras or request.args.get(f'{key}_min') or request.args.get(f'{key}_max')
    ]

    filters = [_sector_dropdown(sectors)]
    filters += [_range_dropdown(key, open_extras) for key in PRIMARY_FILTERS]
    filters += [_range_dropdown(key, open_extras) for key in shown_extras]

    available = [
        {'key': key, 'title': FILTER_PRESETS[key][0], 'url': _url_with(add=open_extras + [key])}
        for key in EXTRA_FILTERS if key not in shown_extras
    ]
    return filters, available


def _previous_prices(asset_ids):
    """Price at each asset's second-most-recent snapshot, keyed by asset id.

    The cards show the move since the last snapshot. There is no intraday
    price stored for the whole universe — the company page fetches a live
    quote for one symbol, which doesn't scale to a page of 24 — so this is
    snapshot-to-snapshot, and it stays empty until a second sweep has run."""
    if not asset_ids:
        return {}
    ranked = (
        db.session.query(
            Fundamentals.asset_id.label('asset_id'),
            Fundamentals.price.label('price'),
            func.row_number().over(
                partition_by=Fundamentals.asset_id,
                order_by=Fundamentals.as_of_date.desc(),
            ).label('rank'),
        )
        .filter(Fundamentals.asset_id.in_(asset_ids))
        .subquery()
    )
    rows = (
        db.session.query(ranked.c.asset_id, ranked.c.price)
        .filter(ranked.c.rank == 2, ranked.c.price.isnot(None))
        .all()
    )
    return {asset_id: price for asset_id, price in rows}


def _price_changes(rows):
    """Percent change against the previous snapshot, per asset id."""
    previous = _previous_prices([asset.id for asset, _ in rows])
    changes = {}
    for asset, fundamentals in rows:
        before = previous.get(asset.id)
        price = getattr(fundamentals, 'price', None)
        if before and price is not None:
            changes[asset.id] = (price - before) / before * 100
    return changes


@stocks_bp.route('/stocks', methods=['GET'])
@login_required
def get_stocks():
    page = request.args.get('page', 1, type=int)
    view = request.args.get('view', 'list')
    if view not in VIEWS:
        view = 'list'

    sort, direction = _current_sort()
    query = _apply_sort(_apply_filters(_latest_fundamentals_query()), sort, direction)
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)

    exchanges = [
        row[0] for row in
        db.session.query(Asset.exchange).distinct().order_by(Asset.exchange).all()
    ]
    sectors = [
        row[0] for row in
        db.session.query(Asset.sector).filter(Asset.sector.isnot(None)).distinct().order_by(Asset.sector).all()
    ]
    filters, available_filters = _toolbar_filters(sectors)

    # Pagination links are the current URL with `page` appended, so they carry
    # every filter, the sort and the layout along with them.
    page_url_base = _url_with()
    page_url_prefix = page_url_base + ('&' if '?' in page_url_base else '?') + 'page='

    context = {
        'rows': pagination.items,
        'pagination': pagination,
        'columns': COLUMNS,
        'view': view,
        'view_urls': {name: _url_with(view=name) for name in VIEWS},
        'exchange_chips': _exchange_chips(exchanges),
        'filters': filters,
        'available_filters': available_filters,
        'total_assets': db.session.query(func.count(Asset.id)).scalar(),
        'last_update': db.session.query(func.max(Fundamentals.as_of_date)).scalar(),
        'export_url': f"/stocks/export.csv?{request.query_string.decode()}",
        'page_url_prefix': page_url_prefix,
        'roe_strong': ROE_STRONG,
        'payout_overpaying': PAYOUT_OVERPAYING,
        'sort': sort,
        'dir': direction,
        'sort_links': _sort_links(sort, direction),
    }
    # Only the cards show a price move, and it costs an extra query.
    context['price_changes'] = _price_changes(pagination.items) if view == 'cards' else {}

    template = 'partials/screener_table.html' if request.headers.get('HX-Request') else 'stocks/screener.html'
    response = make_response(render_template(template, **context))
    # /stocks has two representations for the same URL: a complete document
    # and an HTMX fragment. Without Vary a browser/proxy cache may hand the
    # fragment to a normal navigation (or a full page to an HTMX swap).
    response.vary.add('HX-Request')
    return response


@stocks_bp.route('/stocks/export.csv', methods=['GET'])
@login_required
def export_stocks_csv():
    sort, direction = _current_sort()
    query = _apply_sort(_apply_filters(_latest_fundamentals_query()), sort, direction)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_FIELDS)
    for asset, fundamentals in query.all():
        writer.writerow([
            getattr(asset if field in ASSET_FIELDS else fundamentals, field, None)
            for field in EXPORT_FIELDS
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
        'insight': build_company_insight(asset, fundamentals),
        'key_stat_help': KEY_STAT_HELP,
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
