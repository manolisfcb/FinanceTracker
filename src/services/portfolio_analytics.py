"""Portfolio allocation, income and benchmark analytics for the portfolio page."""

from collections import defaultdict
from datetime import date
import time

import requests

from src.models import Asset, DividendReceived, PortfolioSnapshotModel
from src.services.market_data import get_provider
from src.services.portfolio import fx_rate_to_cad_today


ASSET_CLASSES = (
    {
        'key': 'EQUITY_ETF',
        'label': 'Acciones / ETF',
        'short_label': 'Acciones',
        'color': '#b3372b',
        'target_field': 'equity_etf_percent',
    },
    {
        'key': 'REIT',
        'label': 'REITs',
        'short_label': 'REITs',
        'color': '#b98a2e',
        'target_field': 'reit_percent',
    },
    {
        'key': 'CRYPTO',
        'label': 'Cripto',
        'short_label': 'Cripto',
        'color': '#4a6b8a',
        'target_field': 'crypto_percent',
    },
    {
        'key': 'CASH',
        'label': 'Cash',
        'short_label': 'Cash',
        'color': '#8a857a',
        'target_field': 'cash_percent',
    },
)

DEFAULT_TARGETS = {
    'equity_etf_percent': 40.0,
    'reit_percent': 30.0,
    'crypto_percent': 20.0,
    'cash_percent': 10.0,
}

# CAD-listed investable proxies keep every equity comparison in the user's
# reporting currency. The interest-rate comparison is built separately from
# the Bank of Canada's official overnight target series.
BENCHMARKS = (
    ('XIC.TO', 'S&P/TSX (XIC)', '#1a7f4e'),
    ('VFV.TO', 'S&P 500 (VFV)', '#4a6b8a'),
    ('QQC.TO', 'Nasdaq-100 (QQC)', '#7d5ba6'),
)

_BOC_CACHE_TTL_SECONDS = 3600
_boc_rate_cache: dict[str, tuple[float, dict[str, float]]] = {}


def _canadian_policy_rate_return(start_date: str) -> dict[str, float]:
    """Theoretical cumulative cash return from BoC overnight target V39079.

    V39079 is an annualized policy rate, not an investment price. We compound
    the last published rate over the calendar days until the next observation
    so the result can share a cumulative-return axis with the portfolio.
    """
    cached = _boc_rate_cache.get(start_date)
    if cached and time.monotonic() - cached[0] < _BOC_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        response = requests.get(
            'https://www.bankofcanada.ca/valet/observations/V39079/json',
            params={'start_date': start_date},
            timeout=5,
        )
        response.raise_for_status()
        observations = response.json().get('observations', [])
    except (requests.RequestException, ValueError, TypeError):
        return cached[1] if cached else {}

    points = []
    for observation in observations:
        try:
            points.append((
                date.fromisoformat(observation['d']),
                float(observation['V39079']['v']),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    if not points:
        return cached[1] if cached else {}

    result = {points[0][0].isoformat(): 0.0}
    growth = 1.0
    previous_day, previous_rate = points[0]
    for day, annual_rate in points[1:]:
        elapsed_days = max((day - previous_day).days, 0)
        growth *= (1 + previous_rate / 100 / 365) ** elapsed_days
        result[day.isoformat()] = (growth - 1) * 100
        previous_day, previous_rate = day, annual_rate

    _boc_rate_cache[start_date] = (time.monotonic(), result)
    return result


def classify_asset(asset: Asset) -> str:
    """Map the existing catalog metadata to the four strategic buckets."""
    sector = (asset.sector or '').lower()
    industry = (asset.industry or '').lower()
    name = (asset.name or '').lower()

    if asset.exchange == 'CRYPTO' or sector == 'cryptoassets' or industry == 'cryptocurrency':
        return 'CRYPTO'
    if (
        industry.startswith('reit')
        or ' reit' in f' {name}'
        or (sector == 'etfs' and 'real estate' in industry)
    ):
        return 'REIT'
    return 'EQUITY_ETF'


def asset_segment(asset: Asset, asset_class: str) -> str:
    """Second level used by the composition flow diagram."""
    if asset_class == 'CRYPTO':
        return asset.symbol
    if asset_class == 'REIT':
        industry = asset.industry or 'Inmobiliario'
        return industry.replace('REIT - ', '').replace('REIT—', '').strip()
    if asset.sector == 'ETFs':
        return asset.industry or 'ETF diversificado'
    return asset.sector or asset.industry or 'Sin clasificar'


class PortfolioAnalyticsService:
    def __init__(self, user_id: int):
        self.user_id = user_id

    def allocation(self, positions: list[dict], assets_by_id: dict[int, Asset], plan) -> dict:
        cash_balance = float(plan.cash_balance_cad or 0.0) if plan else 0.0
        values = defaultdict(float)
        segments = defaultdict(float)

        for position in positions:
            asset = assets_by_id.get(position['asset_id'])
            if asset is None:
                continue
            value = position['market_value_cad'] or 0.0
            asset_class = classify_asset(asset)
            values[asset_class] += value
            segments[(asset_class, asset_segment(asset, asset_class))] += value
        values['CASH'] += cash_balance

        total = sum(values.values())
        rows = []
        for meta in ASSET_CLASSES:
            target = (
                float(getattr(plan, meta['target_field']))
                if plan is not None
                else DEFAULT_TARGETS[meta['target_field']]
            )
            current_value = values[meta['key']]
            current_percent = (current_value / total * 100) if total else 0.0
            target_value = total * target / 100
            rows.append({
                **meta,
                'target_percent': target,
                'current_percent': current_percent,
                'current_value_cad': current_value,
                'target_value_cad': target_value,
                'amount_to_trade_cad': target_value - current_value,
                'amount_to_trade_abs_cad': abs(target_value - current_value),
                'deviation': current_percent - target,
            })

        flows = []
        for row in rows:
            if row['current_value_cad'] <= 0:
                continue
            flows.append({
                'from': 'Cartera',
                'to': row['label'],
                'flow': round(row['current_value_cad'], 2),
                'classKey': row['key'],
            })
        for (asset_class, segment), value in sorted(
            segments.items(), key=lambda item: item[1], reverse=True
        ):
            if value <= 0:
                continue
            class_meta = next(item for item in ASSET_CLASSES if item['key'] == asset_class)
            flows.append({
                'from': class_meta['label'],
                'to': f'{segment} · {class_meta["short_label"]}',
                'flow': round(value, 2),
                'classKey': asset_class,
            })
        if cash_balance > 0:
            flows.append({
                'from': 'Cash',
                'to': 'Efectivo CAD',
                'flow': round(cash_balance, 2),
                'classKey': 'CASH',
            })

        return {
            'rows': rows,
            'labels': [row['label'] for row in rows],
            'target_values': [row['target_percent'] for row in rows],
            'current_values': [row['current_percent'] for row in rows],
            'colors': [row['color'] for row in rows],
            'total_cad': total,
            'flows': flows,
            'has_holdings': total > 0,
        }

    def dividends_by_asset(self, assets_by_id: dict[int, Asset]) -> list[dict]:
        totals = defaultdict(lambda: {'received_cad': 0.0, 'per_share_cad': 0.0})
        fx_cache = {'CAD': 1.0}
        rows = DividendReceived.query.filter_by(user_id=self.user_id, confirmed=True).all()
        for dividend in rows:
            asset = assets_by_id.get(dividend.asset_id)
            if asset is None:
                continue
            if dividend.currency not in fx_cache:
                fx_cache[dividend.currency] = fx_rate_to_cad_today(dividend.currency)
            fx_rate = fx_cache[dividend.currency]
            if fx_rate is None:
                continue
            item = totals[asset.symbol]
            item['received_cad'] += dividend.total_amount * fx_rate
            if dividend.quantity_held:
                item['per_share_cad'] += dividend.total_amount / dividend.quantity_held * fx_rate

        return [
            {'symbol': symbol, **values}
            for symbol, values in sorted(
                totals.items(), key=lambda item: item[1]['received_cad'], reverse=True
            )
        ]

    def performance(self) -> dict:
        snapshots = (
            PortfolioSnapshotModel.query.filter_by(user_id=self.user_id, account_id=None)
            .filter(PortfolioSnapshotModel.total_invested_cad > 0)
            .order_by(PortfolioSnapshotModel.date.asc())
            .all()
        )
        if len(snapshots) < 2:
            return {'labels': [], 'series': [], 'has_data': False}

        first_factor = (
            snapshots[0].patrimony_cad + snapshots[0].dividends_accum_cad
        ) / snapshots[0].total_invested_cad
        if not first_factor:
            return {'labels': [], 'series': [], 'has_data': False}

        series_maps = {}
        portfolio_points = {}
        for snapshot in snapshots:
            factor = (
                snapshot.patrimony_cad + snapshot.dividends_accum_cad
            ) / snapshot.total_invested_cad
            portfolio_points[snapshot.date.isoformat()] = (factor / first_factor - 1) * 100
        series_maps['Cartera'] = portfolio_points

        provider = get_provider(max_retries=1, min_interval_seconds=0)
        start_date = snapshots[0].date.isoformat()
        benchmark_meta = []
        for symbol, label, color in BENCHMARKS:
            try:
                history = provider.get_price_history(symbol, '5Y')
            except Exception:
                history = []
            history = [point for point in history if point['date'] >= start_date and point['close']]
            if not history:
                continue
            base = history[0]['close']
            series_maps[label] = {
                point['date']: (point['close'] / base - 1) * 100
                for point in history
            }
            benchmark_meta.append((label, color))

        policy_rate_points = _canadian_policy_rate_return(start_date)
        if policy_rate_points:
            series_maps['Tasa BoC acumulada'] = policy_rate_points
            benchmark_meta.append(('Tasa BoC acumulada', '#b98a2e'))

        labels = sorted({day for points in series_maps.values() for day in points})
        series = [{
            'label': 'Cartera',
            'color': '#b3372b',
            'data': [round(portfolio_points[day], 4) if day in portfolio_points else None for day in labels],
        }]
        for label, color in benchmark_meta:
            points = series_maps[label]
            series.append({
                'label': label,
                'color': color,
                'data': [round(points[day], 4) if day in points else None for day in labels],
            })

        return {'labels': labels, 'series': series, 'has_data': bool(labels)}
