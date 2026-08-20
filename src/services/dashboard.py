"""Dashboard: the whole portfolio on one screen.

Composes PortfolioService (positions, P&L) and DividendsService (income)
rather than recomputing either, so a figure shown here and the same figure
on /portfolio or /dividends can't drift apart. Everything here is a read.

The donut and the contribution bars are drawn as plain SVG rather than with
Chart.js, so their geometry is computed here — in one testable place —
instead of being assembled from arithmetic scattered through the template.
"""
from collections import defaultdict
from datetime import date, datetime, time
from math import pi
from zoneinfo import ZoneInfo

from src import MONTHS_ES
from src.models import (
    Asset,
    CompanyEvent,
    CompanyEventKind,
    DividendHistory,
    OrderModel,
    OrderType,
    PortfolioSnapshotModel,
)
from src.services.dividends import DividendsService
from src.services.portfolio import PortfolioService, fx_rate_to_cad_today

# Slice colours in order; everything past the fifth sector is pooled into
# "Otros" and painted in the neutral.
SLICE_COLORS = ('#b3372b', '#b98a2e', '#1a7f4e', '#4a6b8a', '#7d5ba6')
OTHER_COLOR = '#d9d5cb'
MAX_SLICES = 5

CURRENCY_COLORS = {'CAD': '#b3372b', 'USD': '#4a6b8a'}
DEFAULT_CURRENCY_COLOR = '#b98a2e'

# Donut geometry, in the SVG's own 140x140 user units. The slices are dash
# segments on a single circle, so each one needs the arc length it covers,
# the gap that hides the rest of the circle, and the offset that rotates it
# behind the slices already drawn.
DONUT_RADIUS = 56
DONUT_CIRCUMFERENCE = 2 * pi * DONUT_RADIUS

# Contribution bar geometry, in the SVG's own 340x170 user units.
CONTRIBUTION_MONTHS = 12
BAR_WIDTH = 16
BAR_PITCH = 28
BAR_FIRST_X = 8
BAR_BASELINE = 160
BAR_MAX_HEIGHT = 130

# Regular TSX/NYSE session. Holidays aren't modelled — a closed-for-holiday
# weekday reads as open, which is a cosmetic subtitle being wrong, not a
# number being wrong.
MARKET_TZ = ZoneInfo('America/Toronto')
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

MONTH_INITIALS_ES = tuple(name[0].upper() for name in MONTHS_ES)

# How an event renders in the "Próximos eventos" list: tile background, icon
# stroke, and which icon the template draws.
EVENT_STYLES = {
    CompanyEventKind.DIVIDEND: {'background': '#f3ece3', 'color': '#b98a2e', 'icon': 'clock'},
    CompanyEventKind.EARNINGS: {'background': '#e9efe9', 'color': '#1a7f4e', 'icon': 'trend'},
    CompanyEventKind.FILING: {'background': '#eceef2', 'color': '#4a6b8a', 'icon': 'file'},
    CompanyEventKind.NEWS: {'background': '#f0eee8', 'color': '#6f6b60', 'icon': 'news'},
}

# Events the calendar backfills with once the genuinely upcoming ones run
# out. NEWS is deliberately absent: it arrives by the hundreds and has its
# own page, and it would crowd out the dated events this card exists for.
BACKFILL_KINDS = (CompanyEventKind.FILING, CompanyEventKind.EARNINGS)


def _month_start(reference: date, months_back: int) -> date:
    year, month = reference.year, reference.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


class DashboardService:
    def __init__(self, user_id: int, today: date | None = None):
        self.user_id = user_id
        self.today = today or date.today()
        self.portfolio = PortfolioService(user_id)
        self.dividends = DividendsService(user_id)
        # Both services would otherwise walk the order history and price the
        # lots separately; sharing one instance means that work happens once
        # per request, and that both read the same numbers.
        self.dividends.portfolio = self.portfolio

    @property
    def warnings(self) -> list[str]:
        return self.portfolio.warnings + self.dividends.warnings

    # -- header -------------------------------------------------------------

    def market_status(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(MARKET_TZ)
        is_open = now.weekday() < 5 and MARKET_OPEN <= now.time() < MARKET_CLOSE
        return {
            'open': is_open,
            'label': 'Mercados abiertos' if is_open else 'Mercados cerrados',
        }

    # -- KPI band -----------------------------------------------------------

    def kpis(self) -> dict:
        totals = self.portfolio.get_totals()
        patrimony = totals['patrimony_cad'] or 0.0
        invested = totals['total_invested_cad'] or 0.0
        # Same definition as the Portafolio page's headline gain: what the
        # positions are worth now against what they cost.
        gain = patrimony - invested

        dividend_kpis = self.dividends.kpis(today=self.today)
        projection = dividend_kpis['projection_12m_cad']
        previous, latest = self._last_two_snapshots()

        return {
            'patrimony_cad': patrimony,
            'invested_cad': invested,
            'gain_cad': gain,
            'gain_percent': (gain / invested * 100) if invested else None,
            'change_percent': (
                (latest.patrimony_cad - previous.patrimony_cad) / previous.patrimony_cad * 100
                if previous is not None and latest is not None and previous.patrimony_cad
                else None
            ),
            'change_since': previous.date if previous is not None else None,
            'change_is_today': latest is not None and latest.date == self.today,
            'dividends_12m_cad': dividend_kpis['received_12m_cad'],
            'dividends_monthly_average_cad': dividend_kpis['monthly_average_cad'],
            'projection_12m_cad': projection,
            # Yield on cost: the forward annual payout measured against what
            # the shares cost, not against what they're worth today.
            'yield_on_cost_percent': (projection / invested * 100) if invested else None,
        }

    def _last_two_snapshots(self):
        rows = (
            PortfolioSnapshotModel.query.filter_by(user_id=self.user_id, account_id=None)
            .order_by(PortfolioSnapshotModel.date.desc())
            .limit(2)
            .all()
        )
        if len(rows) < 2:
            return None, (rows[0] if rows else None)
        return rows[1], rows[0]

    # -- equity curve -------------------------------------------------------

    def equity_series(self) -> dict:
        """Patrimonio vs. aportado, one point per daily snapshot.

        The whole history goes to the client; the 1M/6M/1A/Todo switch is a
        slice of these arrays, not a round trip.
        """
        snapshots = (
            PortfolioSnapshotModel.query.filter_by(user_id=self.user_id, account_id=None)
            .order_by(PortfolioSnapshotModel.date.asc())
            .all()
        )
        return {
            'dates': [s.date.strftime('%Y-%m-%d') for s in snapshots],
            'labels': [f"{MONTHS_ES[s.date.month - 1][:3]} {s.date:%y}" for s in snapshots],
            'patrimony': [s.patrimony_cad for s in snapshots],
            'contributed': [s.total_invested_cad for s in snapshots],
        }

    # -- allocation ---------------------------------------------------------

    def sector_allocation(self) -> list[dict]:
        positions = self.portfolio.get_positions_by_asset()
        if not positions:
            return []

        assets = {
            a.id: a
            for a in Asset.query.filter(Asset.id.in_([p['asset_id'] for p in positions])).all()
        }
        by_sector: dict[str, float] = defaultdict(float)
        for position in positions:
            asset = assets.get(position['asset_id'])
            if asset is None:
                continue
            by_sector[asset.sector or 'Sin clasificar'] += position['market_value_cad'] or 0.0

        ranked = sorted(by_sector.items(), key=lambda item: item[1], reverse=True)
        slices = [
            {'label': label, 'value_cad': value, 'color': SLICE_COLORS[i]}
            for i, (label, value) in enumerate(ranked[:MAX_SLICES])
        ]
        rest = sum(value for _, value in ranked[MAX_SLICES:])
        if rest:
            slices.append({'label': 'Otros', 'value_cad': rest, 'color': OTHER_COLOR})

        return self._with_donut_geometry(slices)

    @staticmethod
    def _with_donut_geometry(slices: list[dict]) -> list[dict]:
        total = sum(item['value_cad'] for item in slices)
        if not total:
            return []
        offset = 0.0
        for item in slices:
            share = item['value_cad'] / total
            length = share * DONUT_CIRCUMFERENCE
            item['percent'] = share * 100
            item['dash'] = round(length, 2)
            item['gap'] = round(DONUT_CIRCUMFERENCE - length, 2)
            item['offset'] = round(-offset, 2)
            offset += length
        return slices

    def currency_allocation(self) -> list[dict]:
        by_currency: dict[str, float] = defaultdict(float)
        for lot in self.portfolio.get_positions():
            if lot.quantity <= 0 or lot.market_value_cad is None:
                continue
            by_currency[lot.currency] += lot.market_value_cad

        total = sum(by_currency.values())
        if not total:
            return []
        return [
            {
                'currency': currency,
                'value_cad': value,
                'percent': value / total * 100,
                'color': CURRENCY_COLORS.get(currency, DEFAULT_CURRENCY_COLOR),
            }
            for currency, value in sorted(by_currency.items(), key=lambda item: item[1], reverse=True)
        ]

    # -- contributions ------------------------------------------------------

    def monthly_contributions(self, months: int = CONTRIBUTION_MONTHS) -> dict:
        """Cash put to work per month: what the BUY orders cost, in CAD.

        Sales don't net off — this answers "how much did I feed the
        portfolio", which a sale doesn't undo.
        """
        first_month = _month_start(self.today, months - 1)
        totals: dict[date, float] = defaultdict(float)
        orders = OrderModel.query.filter_by(user_id=self.user_id, type=OrderType.BUY).all()
        for order in orders:
            month = order.executed_at.date().replace(day=1)
            if month < first_month:
                continue
            totals[month] += (order.quantity * order.price + order.fees) * order.fx_rate_to_cad

        months_window = [_month_start(self.today, offset) for offset in range(months - 1, -1, -1)]
        peak = max((totals.get(month, 0.0) for month in months_window), default=0.0)

        bars = []
        for index, month in enumerate(months_window):
            total_cad = totals.get(month, 0.0)
            height = (total_cad / peak * BAR_MAX_HEIGHT) if peak > 0 else 0.0
            is_current = month.year == self.today.year and month.month == self.today.month
            bars.append({
                'month': month,
                'month_name': MONTHS_ES[month.month - 1],
                'initial': MONTH_INITIALS_ES[month.month - 1],
                'total_cad': total_cad,
                'x': BAR_FIRST_X + index * BAR_PITCH,
                'y': round(BAR_BASELINE - height, 2),
                'height': round(height, 2),
                'width': BAR_WIDTH,
                'color': SLICE_COLORS[0] if is_current else OTHER_COLOR,
                'is_current': is_current,
            })

        current = next((bar for bar in bars if bar['is_current']), bars[-1] if bars else None)
        return {
            'bars': bars,
            'current': current,
            'total_cad': sum(bar['total_cad'] for bar in bars),
        }

    # -- top positions ------------------------------------------------------

    def top_positions(self, limit: int = 5) -> list[dict]:
        positions = self.portfolio.get_positions_by_asset()
        if not positions:
            return []

        assets = {
            a.id: a
            for a in Asset.query.filter(Asset.id.in_([p['asset_id'] for p in positions])).all()
        }
        rows = []
        for position in positions:
            asset = assets.get(position['asset_id'])
            if asset is None:
                continue
            rows.append({
                'symbol': asset.symbol,
                'exchange': asset.exchange,
                'market_value_cad': position['market_value_cad'] or 0.0,
                'percent_return': position['percent_return'],
            })
        rows.sort(key=lambda row: row['market_value_cad'], reverse=True)
        return rows[:limit]

    # -- upcoming events ----------------------------------------------------

    def upcoming_events(self, limit: int = 4) -> list[dict]:
        positions = {p['asset_id']: p for p in self.portfolio.get_positions_by_asset()}
        if not positions:
            return []

        upcoming = (
            CompanyEvent.query.filter(
                CompanyEvent.asset_id.in_(positions),
                CompanyEvent.event_date.isnot(None),
                CompanyEvent.event_date >= self.today,
            )
            .order_by(CompanyEvent.event_date.asc())
            .limit(limit)
            .all()
        )

        events = list(upcoming)
        if len(events) < limit:
            already = {event.id for event in events}
            recent = (
                CompanyEvent.query.filter(
                    CompanyEvent.asset_id.in_(positions),
                    CompanyEvent.kind.in_(BACKFILL_KINDS),
                )
                .order_by(CompanyEvent.published_at.desc())
                .limit(limit * 3)
                .all()
            )
            events.extend([e for e in recent if e.id not in already][: limit - len(events)])

        if not events:
            return []

        asset_ids = {event.asset_id for event in events}
        assets = {a.id: a for a in Asset.query.filter(Asset.id.in_(asset_ids)).all()}
        last_amounts = self._last_dividend_amounts(asset_ids)

        entries = []
        for event in events:
            asset = assets.get(event.asset_id)
            if asset is None:
                continue
            style = EVENT_STYLES[event.kind]
            is_upcoming = event.event_date is not None and event.event_date >= self.today
            entry = {
                'symbol': asset.symbol,
                'title': event.title,
                'url': event.url,
                'kind': event.kind,
                'date': event.event_date if is_upcoming else event.published_at.date(),
                'is_upcoming': is_upcoming,
                'amount_per_share': None,
                'currency': asset.currency,
                'estimated_cad': None,
                **style,
            }
            if event.kind == CompanyEventKind.DIVIDEND:
                amount = last_amounts.get(event.asset_id)
                quantity = positions[event.asset_id]['quantity']
                entry['amount_per_share'] = amount
                fx_rate = fx_rate_to_cad_today(asset.currency)
                if amount and fx_rate is not None:
                    entry['estimated_cad'] = amount * quantity * fx_rate
            entries.append(entry)
        return entries

    @staticmethod
    def _last_dividend_amounts(asset_ids) -> dict[int, float]:
        amounts: dict[int, float] = {}
        rows = (
            DividendHistory.query.filter(DividendHistory.asset_id.in_(asset_ids))
            .order_by(DividendHistory.asset_id.asc(), DividendHistory.ex_date.desc())
            .all()
        )
        for row in rows:
            amounts.setdefault(row.asset_id, row.amount)
        return amounts
