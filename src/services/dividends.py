"""Dividend income: what was received, what's coming, and yield on cost.

Composes PortfolioService rather than extending it — positions/P&L and
dividend income are separate concerns, and this module needs the position
data as an input, not as a base class.

Yield on cost mixes an annual dividend rate converted at today's FX with a
cost basis that is FX-locked at trade time. That's the same intentional
asymmetry documented in portfolio.py, not a bug to reconcile.
"""
from collections import defaultdict
from datetime import date, timedelta
from statistics import median

from src.models import (
    Asset,
    CompanyEvent,
    CompanyEventKind,
    DividendHistory,
    DividendReceived,
    Fundamentals,
)
from src.services.portfolio import PortfolioService, fx_rate_to_cad_today

_FREQUENCY_BY_MAX_DAYS = ((45, "Mensual"), (135, "Trimestral"), (270, "Semestral"))


def _months_ago(reference: date, months: int) -> date:
    year = reference.year
    month = reference.month - months
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _infer_frequency(ex_dates: list[date]) -> str | None:
    if len(ex_dates) < 2:
        return None
    recent = sorted(ex_dates)[-6:]
    gaps = [(later - earlier).days for earlier, later in zip(recent, recent[1:])]
    typical = median(gaps)
    for max_days, label in _FREQUENCY_BY_MAX_DAYS:
        if typical < max_days:
            return label
    return "Anual"


class DividendsService:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.portfolio = PortfolioService(user_id)
        self.warnings: list[str] = []
        self._fx_cache: dict[str, float | None] = {}

    # -- helpers ------------------------------------------------------------

    def _to_cad(self, amount: float, currency: str) -> float | None:
        if currency not in self._fx_cache:
            self._fx_cache[currency] = fx_rate_to_cad_today(currency)
            if self._fx_cache[currency] is None:
                # Otherwise real dividends would silently render as C$0.00.
                self.warnings.append(
                    f"no hay FxRate {currency}->CAD: los dividendos en {currency} quedan excluidos"
                )
        rate = self._fx_cache[currency]
        return amount * rate if rate is not None else None

    def _received_rows(self) -> list[DividendReceived]:
        """Confirmed plus still-pending suggestions — dismissed ones are out."""
        return (
            DividendReceived.query.filter_by(user_id=self.user_id, dismissed=False)
            .order_by(DividendReceived.pay_date.asc())
            .all()
        )

    @staticmethod
    def _latest_fundamentals(asset_ids) -> dict[int, Fundamentals]:
        if not asset_ids:
            return {}
        rows = (
            Fundamentals.query.filter(Fundamentals.asset_id.in_(asset_ids))
            .order_by(Fundamentals.asset_id.asc(), Fundamentals.as_of_date.desc())
            .all()
        )
        latest: dict[int, Fundamentals] = {}
        for row in rows:
            latest.setdefault(row.asset_id, row)
        return latest

    def _positions(self) -> dict[int, dict]:
        return {p["asset_id"]: p for p in self.portfolio.get_positions_by_asset()}

    # -- public reads -------------------------------------------------------

    def monthly_received(self, months: int = 12, today: date | None = None) -> list[dict]:
        today = today or date.today()
        first_month = _months_ago(today, months - 1)

        totals: dict[tuple[int, int], float] = defaultdict(float)
        for row in self._received_rows():
            if row.pay_date < first_month:
                continue
            amount_cad = self._to_cad(row.total_amount, row.currency)
            if amount_cad is None:
                continue
            totals[(row.pay_date.year, row.pay_date.month)] += amount_cad

        series = []
        for offset in range(months - 1, -1, -1):
            month_start = _months_ago(today, offset)
            series.append({
                "month": month_start,
                "total_cad": totals.get((month_start.year, month_start.month), 0.0),
            })
        return series

    def received_between(self, start: date, end: date) -> float:
        total = 0.0
        for row in self._received_rows():
            if not (start <= row.pay_date < end):
                continue
            amount_cad = self._to_cad(row.total_amount, row.currency)
            if amount_cad is not None:
                total += amount_cad
        return total

    def by_position(self, today: date | None = None) -> list[dict]:
        today = today or date.today()
        twelve_months_ago = today - timedelta(days=365)

        positions = self._positions()
        received_12m: dict[int, float] = defaultdict(float)
        received_total: dict[int, float] = defaultdict(float)
        for row in self._received_rows():
            amount_cad = self._to_cad(row.total_amount, row.currency)
            if amount_cad is None:
                continue
            received_total[row.asset_id] += amount_cad
            if row.pay_date >= twelve_months_ago:
                received_12m[row.asset_id] += amount_cad

        asset_ids = set(positions) | set(received_total)
        if not asset_ids:
            return []

        assets = {a.id: a for a in Asset.query.filter(Asset.id.in_(asset_ids)).all()}
        fundamentals = self._latest_fundamentals(asset_ids)

        ex_dates_by_asset: dict[int, list[date]] = defaultdict(list)
        for row in DividendHistory.query.filter(DividendHistory.asset_id.in_(asset_ids)).all():
            ex_dates_by_asset[row.asset_id].append(row.ex_date)

        total_12m = sum(received_12m.values())
        rows = []
        for asset_id in asset_ids:
            asset = assets.get(asset_id)
            if asset is None:
                continue
            position = positions.get(asset_id)
            snapshot = fundamentals.get(asset_id)
            dividend_rate = snapshot.dividend_rate if snapshot else None

            yoc = None
            if position and dividend_rate and position["avg_cost_cad"]:
                rate_cad = self._to_cad(dividend_rate, asset.currency)
                if rate_cad is not None:
                    yoc = rate_cad / position["avg_cost_cad"]

            rows.append({
                "asset_id": asset_id,
                "symbol": asset.symbol,
                "name": asset.name,
                "exchange": asset.exchange,
                "quantity": position["quantity"] if position else 0.0,
                "current_yield": snapshot.dividend_yield if snapshot else None,
                "yoc": yoc,
                "received_12m_cad": received_12m.get(asset_id, 0.0),
                "received_total_cad": received_total.get(asset_id, 0.0),
                "frequency": _infer_frequency(ex_dates_by_asset.get(asset_id, [])),
                "income_share_percent": (
                    received_12m.get(asset_id, 0.0) / total_12m * 100 if total_12m else None
                ),
            })

        rows.sort(key=lambda row: row["received_12m_cad"], reverse=True)
        return rows

    def projection_12m(self) -> float:
        """Annual dividend rate times shares held, at the current payout rate."""
        positions = self._positions()
        if not positions:
            return 0.0

        assets = {a.id: a for a in Asset.query.filter(Asset.id.in_(positions)).all()}
        fundamentals = self._latest_fundamentals(positions)

        total = 0.0
        for asset_id, position in positions.items():
            snapshot = fundamentals.get(asset_id)
            asset = assets.get(asset_id)
            if not snapshot or not snapshot.dividend_rate or asset is None:
                continue
            amount_cad = self._to_cad(snapshot.dividend_rate * position["quantity"], asset.currency)
            if amount_cad is not None:
                total += amount_cad
        return total

    def upcoming_calendar(self, limit: int = 8, today: date | None = None) -> list[dict]:
        today = today or date.today()
        positions = self._positions()
        if not positions:
            return []

        events = (
            CompanyEvent.query.filter(
                CompanyEvent.kind == CompanyEventKind.DIVIDEND,
                CompanyEvent.asset_id.in_(positions),
                CompanyEvent.event_date >= today,
            )
            .order_by(CompanyEvent.event_date.asc())
            .limit(limit)
            .all()
        )
        if not events:
            return []

        asset_ids = {event.asset_id for event in events}
        assets = {a.id: a for a in Asset.query.filter(Asset.id.in_(asset_ids)).all()}
        last_amounts: dict[int, float] = {}
        for row in (
            DividendHistory.query.filter(DividendHistory.asset_id.in_(asset_ids))
            .order_by(DividendHistory.asset_id.asc(), DividendHistory.ex_date.desc())
            .all()
        ):
            last_amounts.setdefault(row.asset_id, row.amount)

        entries = []
        for event in events:
            asset = assets.get(event.asset_id)
            if asset is None:
                continue
            quantity = positions[event.asset_id]["quantity"]
            amount_per_share = last_amounts.get(event.asset_id)
            estimated_cad = (
                self._to_cad(amount_per_share * quantity, asset.currency)
                if amount_per_share
                else None
            )
            entries.append({
                "asset_id": event.asset_id,
                "symbol": asset.symbol,
                "exchange": asset.exchange,
                "event_date": event.event_date,
                "title": event.title,
                "quantity": quantity,
                "amount_per_share": amount_per_share,
                "currency": asset.currency,
                "estimated_cad": estimated_cad,
            })
        return entries

    def kpis(self, today: date | None = None) -> dict:
        today = today or date.today()
        last_12m = self.received_between(today - timedelta(days=365), today + timedelta(days=1))
        previous_12m = self.received_between(today - timedelta(days=730), today - timedelta(days=365))
        upcoming = self.upcoming_calendar(limit=1, today=today)

        return {
            "received_12m_cad": last_12m,
            "change_vs_previous_percent": (
                (last_12m - previous_12m) / previous_12m * 100 if previous_12m else None
            ),
            "monthly_average_cad": last_12m / 12,
            "next_payment": upcoming[0] if upcoming else None,
            "projection_12m_cad": self.projection_12m(),
        }

    def pending_suggestions(self) -> list[dict]:
        rows = (
            DividendReceived.query.filter_by(
                user_id=self.user_id, confirmed=False, dismissed=False
            )
            .order_by(DividendReceived.pay_date.desc())
            .all()
        )
        if not rows:
            return []

        assets = {
            a.id: a
            for a in Asset.query.filter(Asset.id.in_({row.asset_id for row in rows})).all()
        }
        return [
            {
                "id": row.id,
                "symbol": assets[row.asset_id].symbol if row.asset_id in assets else "—",
                "name": assets[row.asset_id].name if row.asset_id in assets else "",
                "pay_date": row.pay_date,
                "quantity_held": row.quantity_held,
                "total_amount": row.total_amount,
                "currency": row.currency,
            }
            for row in rows
        ]
