"""Transparent, read-only equity rankings built from stored fundamentals.

The calculations in this module deliberately stay pure: they never fetch market
data and never mutate a snapshot.  That makes the methodology page fast, keeps
the numbers reproducible for a given fundamentals date, and gives the tests a
small surface on which to verify every formula.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import sqrt


BAZIN_REQUIRED_YIELD = 0.06
BUFFETT_GOOD_SCORE = 70.0
LYNCH_MAX_GROWTH_PE = 25.0

# Yahoo and the static catalogs use a mix of GICS-style and plain-English
# labels for the same economic sector.  Rankings should not split banks or
# health companies into two artificial peer groups just because of spelling.
SECTOR_ALIASES = {
    "Financials": "Financial Services",
    "Information Technology": "Technology",
    "Health Care": "Healthcare",
    "Consumer Discretionary": "Consumer Cyclical",
    "Consumer Staples": "Consumer Defensive",
    "Materials": "Basic Materials",
}


@dataclass(frozen=True)
class MethodDefinition:
    slug: str
    name: str
    short_name: str
    eyebrow: str
    summary: str
    basis: str
    calculation: tuple[str, ...]
    useful_for: str
    caveats: tuple[str, ...]
    result_label: str
    has_fair_value: bool


METHODS = {
    "graham": MethodDefinition(
        slug="graham",
        name="Benjamin Graham",
        short_name="Graham",
        eyebrow="Valor intrínseco y margen de seguridad",
        summary=(
            "Busca empresas rentables cuyo precio sea bajo frente a sus ganancias y a su patrimonio. "
            "La cotización nominal no importa: importa cuánto negocio representa cada acción."
        ),
        basis=(
            "Usamos el Número de Graham, una aproximación para compañías maduras con ganancias y patrimonio "
            "positivos. El factor 22,5 combina los límites clásicos de P/L 15 y P/VP 1,5."
        ),
        calculation=(
            "Precio Graham = √(22,5 × beneficio por acción × valor patrimonial por acción).",
            "Margen de seguridad = (precio Graham ÷ precio actual) − 1.",
            "Se excluyen pérdidas, patrimonio negativo y datos incompletos.",
        ),
        useful_for=(
            "Comparar compañías maduras y con activos tangibles dentro del mismo sector; es especialmente "
            "útil como primera criba de valuación."
        ),
        caveats=(
            "Puede infravalorar negocios de software, marcas y otros activos intangibles.",
            "Un potencial alto puede reflejar ganancias extraordinarias o deterioro del negocio.",
            "El precio calculado no reemplaza revisar deuda, calidad y recurrencia de resultados.",
        ),
        result_label="Potencial Graham",
        has_fair_value=True,
    ),
    "bazin": MethodDefinition(
        slug="bazin",
        name="Décio Bazin",
        short_name="Bazin",
        eyebrow="Renta por dividendos y precio techo",
        summary=(
            "Parte del flujo de dividendos que recibe el accionista. Una acción resulta más atractiva cuando "
            "su dividendo anual permite alcanzar una rentabilidad mínima al precio pagado."
        ),
        basis=(
            "La implementación aplica el rendimiento mínimo clásico del 6% y muestra payout y deuda para "
            "contextualizar la sostenibilidad. Es una criba cuantitativa, no un análisis completo del historial."
        ),
        calculation=(
            "Precio techo = dividendo anual por acción ÷ 0,06.",
            "Potencial = (precio techo ÷ precio actual) − 1.",
            "Si falta el dividendo anual, se estima como precio × dividend yield reportado.",
        ),
        useful_for=(
            "Ordenar empresas maduras que distribuyen efectivo, siempre comparando la estabilidad del dividendo "
            "y las reglas de payout propias de cada sector."
        ),
        caveats=(
            "Un yield alto puede anticipar un recorte del dividendo.",
            "Bancos, utilities y REITs tienen estructuras de capital y payout distintas.",
            "La base actual no prueba todavía una década completa de dividendos sin interrupciones.",
        ),
        result_label="Potencial Bazin",
        has_fair_value=True,
    ),
    "lynch": MethodDefinition(
        slug="lynch",
        name="Peter Lynch",
        short_name="Lynch",
        eyebrow="Precio razonable frente al crecimiento",
        summary=(
            "Relaciona el múltiplo de ganancias con el crecimiento del beneficio. La idea no es comprar "
            "crecimiento a cualquier precio, sino evitar pagar un P/L muy superior a la expansión observada."
        ),
        basis=(
            "Usamos una versión auditable del PEG: un P/L objetivo igual al crecimiento porcentual del BPA más "
            "el yield. Para reducir extrapolaciones, el P/L objetivo se limita a 25."
        ),
        calculation=(
            "P/L objetivo = mín. 25 y máx. 0 de [crecimiento BPA (%) + yield (%)].",
            "Precio Lynch = BPA × P/L objetivo.",
            "Potencial = (precio Lynch ÷ precio actual) − 1.",
        ),
        useful_for=(
            "Comparar empresas rentables en crecimiento dentro de un sector. Complementa a Graham cuando el "
            "patrimonio contable explica poco del valor del negocio."
        ),
        caveats=(
            "El crecimiento reciente no garantiza crecimiento futuro.",
            "Resultados cíclicos o una base anual deprimida pueden inflar el cálculo.",
            "Se omiten compañías con crecimiento o beneficio por acción no positivos.",
        ),
        result_label="Potencial Lynch",
        has_fair_value=True,
    ),
    "greenblatt": MethodDefinition(
        slug="greenblatt",
        name="Joel Greenblatt",
        short_name="Greenblatt",
        eyebrow="Magic Formula: calidad más precio",
        summary=(
            "Combina un negocio que obtiene buen retorno sobre el capital con un precio bajo frente a la "
            "ganancia operativa. No estima un precio justo: ordena candidatos."
        ),
        basis=(
            "Se rankean por separado el earnings yield (EBIT/EV) y el ROIC disponible, y luego se promedian "
            "ambas posiciones dentro de cada sector. Cuando los estados aún no incluyen esos campos, se usa "
            "la aproximación EBITDA/EV y ROA, identificada como proxy en la tabla."
        ),
        calculation=(
            "Earnings yield = EBIT ÷ valor empresa = 1 ÷ EV/EBIT.",
            "Se ordenan earnings yield y ROIC de mayor a menor.",
            "La puntuación 0–100 resume el promedio de ambos puestos en su sector.",
        ),
        useful_for=(
            "Encontrar empresas simultáneamente rentables y baratas sin depender del beneficio neto ni de una "
            "previsión explícita de crecimiento."
        ),
        caveats=(
            "Nuestro ROIC es una aproximación con los estados disponibles; los proxies EBITDA/EV y ROA son aún menos precisos.",
            "No es directamente comparable en bancos y aseguradoras.",
            "Es una herramienta de ranking; no ofrece precio objetivo ni momento de compra.",
        ),
        result_label="Puntuación Greenblatt",
        has_fair_value=False,
    ),
    "buffett": MethodDefinition(
        slug="buffett",
        name="Buffett / Munger",
        short_name="Buffett",
        eyebrow="Calidad a un precio sensato",
        summary=(
            "Prioriza rentabilidad consistente, márgenes y deuda controlada, y después exige que el P/L no "
            "elimine todo el atractivo. No existe una fórmula pública única de Buffett."
        ),
        basis=(
            "La puntuación TrueNorth es una criba inspirada en esos principios: 75% calidad (ROE, ROIC, margen "
            "operativo y deuda) y 25% valuación por P/L. No se presenta como una fórmula del inversor."
        ),
        calculation=(
            "Calidad: ROE objetivo 20%, ROIC 15%, margen operativo 20% y deuda/patrimonio ≤ 1×.",
            "Valuación: máxima puntuación con P/L ≤ 15; por encima disminuye proporcionalmente.",
            "Puntuación final = 75% calidad + 25% valuación, en escala 0–100.",
        ),
        useful_for=(
            "Crear una lista corta de negocios rentables y financieramente sólidos para una revisión cualitativa "
            "más profunda de ventajas competitivas y administración."
        ),
        caveats=(
            "La ventaja competitiva y la calidad gerencial no pueden reducirse a estos ratios.",
            "Faltan series largas para medir estabilidad de márgenes y ganancias durante ciclos completos.",
            "Es una heurística documentada de TrueNorth, no una recomendación ni un valor intrínseco.",
        ),
        result_label="Puntuación calidad/precio",
        has_fair_value=False,
    ),
}


def _positive(value):
    return value is not None and value > 0


def _upside(fair_value, price):
    return fair_value / price - 1


def canonical_sector(sector):
    if not sector:
        return "Sin sector"
    return SECTOR_ALIASES.get(sector, sector)


def _base_result(asset, fundamentals, **values):
    return {
        "asset": asset,
        "fundamentals": fundamentals,
        "sector": canonical_sector(asset.sector),
        **values,
    }


def _graham(asset, fundamentals):
    if not all(_positive(value) for value in (fundamentals.price, fundamentals.eps)):
        return None
    book_value_per_share = fundamentals.book_value_per_share
    # P/VP = precio / VPA, so this is the same reported input recovered
    # algebraically when an older snapshot predates the explicit VPA column.
    if not _positive(book_value_per_share) and _positive(fundamentals.pb):
        book_value_per_share = fundamentals.price / fundamentals.pb
    if not _positive(book_value_per_share):
        return None
    fair_value = sqrt(22.5 * fundamentals.eps * book_value_per_share)
    return _base_result(
        asset,
        fundamentals,
        fair_value=fair_value,
        result=_upside(fair_value, fundamentals.price),
        metric_a=("P/L", fundamentals.pe, "ratio"),
        metric_b=("P/VP", fundamentals.pb, "ratio"),
    )


def _bazin(asset, fundamentals):
    if not _positive(fundamentals.price):
        return None
    annual_dividend = fundamentals.dividend_rate
    if not _positive(annual_dividend) and _positive(fundamentals.dividend_yield):
        annual_dividend = fundamentals.price * fundamentals.dividend_yield
    if not _positive(annual_dividend):
        return None
    fair_value = annual_dividend / BAZIN_REQUIRED_YIELD
    return _base_result(
        asset,
        fundamentals,
        fair_value=fair_value,
        result=_upside(fair_value, fundamentals.price),
        metric_a=("Yield", fundamentals.dividend_yield, "percent"),
        metric_b=("Payout", fundamentals.payout_ratio, "percent"),
    )


def _lynch(asset, fundamentals):
    if not all(_positive(value) for value in (fundamentals.price, fundamentals.eps, fundamentals.eps_growth_5y)):
        return None
    growth_percent = fundamentals.eps_growth_5y * 100
    yield_percent = max(fundamentals.dividend_yield or 0, 0) * 100
    target_pe = min(LYNCH_MAX_GROWTH_PE, growth_percent + yield_percent)
    if target_pe <= 0:
        return None
    fair_value = fundamentals.eps * target_pe
    return _base_result(
        asset,
        fundamentals,
        fair_value=fair_value,
        result=_upside(fair_value, fundamentals.price),
        metric_a=("Crec. BPA", fundamentals.eps_growth_5y, "percent"),
        metric_b=("P/L objetivo", target_pe, "ratio"),
    )


def _greenblatt_candidates(rows):
    by_sector = defaultdict(list)
    for asset, fundamentals in rows:
        if not fundamentals or not _positive(fundamentals.price):
            continue
        if _positive(fundamentals.ev_ebit):
            earnings_yield = 1 / fundamentals.ev_ebit
            earnings_label = "EBIT/EV"
        elif _positive(fundamentals.ev_ebitda):
            earnings_yield = 1 / fundamentals.ev_ebitda
            earnings_label = "EBITDA/EV · proxy"
        else:
            continue

        if _positive(fundamentals.roic):
            capital_return = fundamentals.roic
            return_label = "ROIC"
        elif _positive(fundamentals.roa):
            capital_return = fundamentals.roa
            return_label = "ROA · proxy"
        else:
            continue
        by_sector[canonical_sector(asset.sector)].append(
            (asset, fundamentals, earnings_yield, capital_return, earnings_label, return_label)
        )

    results = []
    for sector, candidates in by_sector.items():
        ey_rank = {
            asset.id: rank
            for rank, (asset, *_rest) in enumerate(sorted(candidates, key=lambda row: row[2], reverse=True), 1)
        }
        roic_rank = {
            asset.id: rank
            for rank, (asset, *_rest) in enumerate(
                sorted(candidates, key=lambda row: row[3], reverse=True), 1
            )
        }
        count = len(candidates)
        for asset, fundamentals, earnings_yield, capital_return, earnings_label, return_label in candidates:
            average_rank = (ey_rank[asset.id] + roic_rank[asset.id]) / 2
            score = 100.0 if count == 1 else 100 * (1 - (average_rank - 1) / (count - 1))
            results.append(_base_result(
                asset,
                fundamentals,
                fair_value=None,
                result=max(0.0, min(100.0, score)),
                metric_a=(earnings_label, earnings_yield, "percent"),
                metric_b=(return_label, capital_return, "percent"),
            ))
    return results


def _cap_ratio(value, target):
    if value is None:
        return None
    return max(0.0, min(1.0, value / target))


def _debt_multiple(value):
    """Yahoo normally reports D/E in percentage points; tolerate 1.x inputs."""
    if value is None:
        return None
    return value / 100 if abs(value) > 5 else value


def _buffett(asset, fundamentals):
    if not fundamentals or not _positive(fundamentals.price) or not _positive(fundamentals.pe):
        return None

    quality_parts = [
        _cap_ratio(fundamentals.roe, 0.20),
        _cap_ratio(fundamentals.roic, 0.15),
        _cap_ratio(fundamentals.operating_margin, 0.20),
    ]
    debt = _debt_multiple(fundamentals.debt_to_equity)
    quality_parts.append(None if debt is None else max(0.0, min(1.0, 1 - debt / 2)))
    available = [part for part in quality_parts if part is not None]
    if len(available) < 3:
        return None

    quality = sum(available) / len(available)
    valuation = min(1.0, 15 / fundamentals.pe)
    score = (quality * 0.75 + valuation * 0.25) * 100
    if fundamentals.roic is not None:
        return_metric = ("ROIC", fundamentals.roic, "percent")
    else:
        return_metric = ("ROE", fundamentals.roe, "percent")
    return _base_result(
        asset,
        fundamentals,
        fair_value=None,
        result=score,
        metric_a=return_metric,
        metric_b=("P/L", fundamentals.pe, "ratio"),
    )


def build_buy_price_rows(rows):
    """Calculate price methods and the Buffett score without dropping assets."""
    calculators = {
        "graham": _graham,
        "bazin": _bazin,
        "lynch": _lynch,
    }
    results = []
    for asset, fundamentals in rows:
        method_results = {
            slug: calculator(asset, fundamentals) if fundamentals else None
            for slug, calculator in calculators.items()
        }
        fair_values = {
            slug: result["fair_value"] if result else None
            for slug, result in method_results.items()
        }
        current_price = fundamentals.price if fundamentals else None
        margins = {
            slug: (value - current_price) / value
            if _positive(value) and _positive(current_price) else None
            for slug, value in fair_values.items()
        }
        available = [value for value in fair_values.values() if value is not None]
        within_price = [
            value for value in available
            if _positive(current_price) and current_price <= value
        ]
        buffett_result = _buffett(asset, fundamentals) if fundamentals else None
        buffett_score = buffett_result["result"] if buffett_result else None
        results.append({
            "asset": asset,
            "fundamentals": fundamentals,
            "fair_values": fair_values,
            "margins": margins,
            "available_count": len(available),
            "within_price_count": len(within_price),
            "buffett_score": buffett_score,
            "buffett_is_good": buffett_score is not None and buffett_score >= BUFFETT_GOOD_SCORE,
        })
    return results


def filter_and_sort_buy_price_rows(rows, method="graham", status="all", order="best"):
    """Filter and order the full buy-price universe by one selected method."""
    method = method if method in ("graham", "bazin", "lynch", "buffett") else "graham"
    status = status if status in ("all", "favorable", "unfavorable", "missing") else "all"
    order = order if order in ("best", "worst", "symbol") else "best"

    def metric(row):
        if method == "buffett":
            return row["buffett_score"]
        return row["margins"][method]

    def favorable(row):
        value = metric(row)
        if value is None:
            return None
        return row["buffett_is_good"] if method == "buffett" else value >= 0

    if status == "missing":
        selected = [row for row in rows if metric(row) is None]
    elif status == "favorable":
        selected = [row for row in rows if favorable(row) is True]
    elif status == "unfavorable":
        selected = [row for row in rows if favorable(row) is False]
    else:
        selected = list(rows)

    if order == "symbol":
        selected.sort(key=lambda row: (row["asset"].symbol, row["asset"].exchange))
    elif order == "worst":
        selected.sort(key=lambda row: (
            metric(row) is None,
            metric(row) if metric(row) is not None else 0,
            row["asset"].symbol,
        ))
    else:
        selected.sort(key=lambda row: (
            metric(row) is None,
            -(metric(row) if metric(row) is not None else 0),
            row["asset"].symbol,
        ))
    return selected


def rank_companies(rows, method_slug):
    """Return eligible companies ranked within explicit sector groups."""
    method_slug = method_slug if method_slug in METHODS else "graham"
    if method_slug == "greenblatt":
        ranked = _greenblatt_candidates(rows)
    else:
        calculator = {
            "graham": _graham,
            "bazin": _bazin,
            "lynch": _lynch,
            "buffett": _buffett,
        }[method_slug]
        ranked = [result for asset, fundamentals in rows if fundamentals for result in [calculator(asset, fundamentals)] if result]

    ranked.sort(key=lambda result: (result["sector"], -result["result"], result["asset"].symbol))
    groups = []
    for sector in sorted({result["sector"] for result in ranked}):
        sector_rows = [result for result in ranked if result["sector"] == sector]
        for position, result in enumerate(sector_rows, 1):
            result["sector_rank"] = position
        groups.append({"sector": sector, "rows": sector_rows})
    return groups
