"""Portfolio positions and P&L, computed on the fly from `Order` rows.

CRA average-cost pooling: non-registered accounts (MARGIN, CASH) share one
Adjusted Cost Base pool per (user, asset) — CRA treats identical property
held in taxable accounts as one taxpayer-level position, regardless of which
specific account or broker holds it. Each registered account (TFSA, RRSP,
FHSA) is its own isolated pool keyed by (account_id, asset) — shares can't
move between registered accounts via ordinary buy/sell, so pooling them
together would misstate book value, not just be tax-technically irrelevant.

CAD cost basis vs. CAD market value are intentionally asymmetric: cost basis
uses each order's own `fx_rate_to_cad` (the rate at trade time — the correct
ACB-in-CAD figure), while current market value uses today's `FxRate` row.
Cost is FX-locked at trade date, value floats with today's rate — that's
correct, not a bug to reconcile.
"""
from dataclasses import dataclass
from datetime import date

from src.models import Account, DividendHistory, DividendReceived, Fundamentals, FxRate, OrderModel, OrderType


@dataclass
class PositionLot:
    asset_id: int
    pool_key: str
    account_ids: list
    quantity_by_account: dict
    quantity: float = 0.0
    currency: str = "CAD"
    avg_cost_original: float = 0.0
    avg_cost_cad: float = 0.0
    realized_pnl_original: float = 0.0
    realized_pnl_cad: float = 0.0
    current_price: float | None = None
    market_value_original: float | None = None
    market_value_cad: float | None = None
    unrealized_pnl_original: float | None = None
    unrealized_pnl_cad: float | None = None
    unrealized_pnl_percent: float | None = None


def _pool_key(asset_id: int, account: Account) -> str:
    if account.is_registered:
        return f"asset:{asset_id}|account:{account.id}"
    return f"asset:{asset_id}|nonreg:{account.user_id}"


def fx_rate_to_cad_today(currency: str) -> float | None:
    """Today's FX rate to convert `currency` into CAD, or None if unknown.

    Shared by PortfolioService (current market value) and anywhere else that
    needs to convert a foreign-currency amount to CAD as of today (e.g. a
    manual order entry route defaulting fx_rate_to_cad for a non-CAD order).
    """
    if currency == "CAD":
        return 1.0
    row = FxRate.query.filter_by(pair=f"{currency}CAD").order_by(FxRate.date.desc()).first()
    return row.rate if row else None


class PortfolioService:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.warnings: list[str] = []
        self._lots: list[PositionLot] | None = None

    # -- pure computation -------------------------------------------------

    def compute_lots(self) -> list[PositionLot]:
        if self._lots is not None:
            return self._lots

        self.warnings = []
        orders = (
            OrderModel.query.join(Account, OrderModel.account_id == Account.id)
            .filter(OrderModel.user_id == self.user_id)
            .order_by(OrderModel.executed_at.asc(), OrderModel.id.asc())
            .all()
        )

        pools: dict[str, PositionLot] = {}
        for order in orders:
            key = _pool_key(order.asset_id, order.account)
            lot = pools.get(key)
            if lot is None:
                lot = PositionLot(
                    asset_id=order.asset_id,
                    pool_key=key,
                    account_ids=[],
                    quantity_by_account={},
                    currency=order.currency,
                )
                pools[key] = lot
            if order.account_id not in lot.account_ids:
                lot.account_ids.append(order.account_id)
            lot.quantity_by_account.setdefault(order.account_id, 0.0)

            self._apply_order(lot, order)

        self._lots = list(pools.values())
        self._price_and_value_lots(self._lots)
        return self._lots

    def _apply_order(self, lot: PositionLot, order: OrderModel):
        qty = order.quantity
        if order.type == OrderType.BUY:
            trade_cost_original = qty * order.price + order.fees
            trade_cost_cad = trade_cost_original * order.fx_rate_to_cad
            new_quantity = lot.quantity + qty
            if new_quantity != 0:
                lot.avg_cost_original = (
                    lot.quantity * lot.avg_cost_original + trade_cost_original
                ) / new_quantity
                lot.avg_cost_cad = (
                    lot.quantity * lot.avg_cost_cad + trade_cost_cad
                ) / new_quantity
            lot.quantity = new_quantity
            lot.quantity_by_account[order.account_id] += qty
        else:
            if qty > lot.quantity:
                self.warnings.append(
                    f"asset {order.asset_id}: sold {qty} but only held {lot.quantity} "
                    f"as of {order.executed_at} (order id {order.id})"
                )
            proceeds_original = qty * order.price - order.fees
            proceeds_cad = proceeds_original * order.fx_rate_to_cad
            lot.realized_pnl_original += proceeds_original - qty * lot.avg_cost_original
            lot.realized_pnl_cad += proceeds_cad - qty * lot.avg_cost_cad
            lot.quantity -= qty
            lot.quantity_by_account[order.account_id] -= qty

    def _price_and_value_lots(self, lots: list[PositionLot]):
        asset_ids = {lot.asset_id for lot in lots}
        prices = self._latest_prices(asset_ids)
        fx_cache: dict[str, float | None] = {}

        for lot in lots:
            lot.current_price = prices.get(lot.asset_id)
            if lot.current_price is None:
                self.warnings.append(f"asset {lot.asset_id}: no current price available")
                continue

            lot.market_value_original = lot.quantity * lot.current_price
            lot.unrealized_pnl_original = lot.market_value_original - lot.quantity * lot.avg_cost_original

            if lot.currency not in fx_cache:
                fx_cache[lot.currency] = fx_rate_to_cad_today(lot.currency)
            fx_rate = fx_cache[lot.currency]

            if fx_rate is None:
                self.warnings.append(
                    f"asset {lot.asset_id}: no FxRate for {lot.currency}->CAD, excluded from CAD totals"
                )
                continue

            lot.market_value_cad = lot.market_value_original * fx_rate
            lot.unrealized_pnl_cad = lot.market_value_cad - lot.quantity * lot.avg_cost_cad
            invested_cad = lot.quantity * lot.avg_cost_cad
            lot.unrealized_pnl_percent = (
                (lot.unrealized_pnl_cad / invested_cad * 100) if invested_cad else None
            )

    @staticmethod
    def _latest_prices(asset_ids) -> dict:
        if not asset_ids:
            return {}
        rows = (
            Fundamentals.query.filter(Fundamentals.asset_id.in_(asset_ids))
            .order_by(Fundamentals.asset_id.asc(), Fundamentals.as_of_date.desc())
            .all()
        )
        prices: dict[int, float | None] = {}
        for row in rows:
            prices.setdefault(row.asset_id, row.price)
        return prices

    # -- public reads -------------------------------------------------------

    def get_positions(self, account_id: int | None = None) -> list[PositionLot]:
        lots = self.compute_lots()
        if account_id is None:
            return lots
        return [lot for lot in lots if account_id in lot.account_ids]

    def get_positions_by_asset(self) -> list[dict]:
        lots = self.compute_lots()
        by_asset: dict[int, dict] = {}
        for lot in lots:
            agg = by_asset.setdefault(
                lot.asset_id,
                {
                    "asset_id": lot.asset_id,
                    "quantity": 0.0,
                    "invested_cad": 0.0,
                    "market_value_cad": 0.0,
                    "unrealized_pnl_cad": 0.0,
                    "realized_pnl_cad": 0.0,
                    "has_market_value": False,
                },
            )
            agg["quantity"] += lot.quantity
            agg["invested_cad"] += lot.quantity * lot.avg_cost_cad
            agg["realized_pnl_cad"] += lot.realized_pnl_cad
            if lot.market_value_cad is not None:
                agg["market_value_cad"] += lot.market_value_cad
                agg["unrealized_pnl_cad"] += lot.unrealized_pnl_cad or 0.0
                agg["has_market_value"] = True

        result = []
        for asset_id, agg in by_asset.items():
            if agg["quantity"] <= 0:
                continue
            avg_cost_cad = agg["invested_cad"] / agg["quantity"] if agg["quantity"] else 0.0
            percent_return = (
                (agg["unrealized_pnl_cad"] / agg["invested_cad"] * 100)
                if agg["has_market_value"] and agg["invested_cad"]
                else None
            )
            result.append(
                {
                    **agg,
                    "avg_cost_cad": avg_cost_cad,
                    "percent_return": percent_return,
                    "current_price": (agg["market_value_cad"] / agg["quantity"]) if agg["has_market_value"] and agg["quantity"] else None,
                }
            )
        return result

    def get_totals(self, account_id: int | None = None) -> dict:
        lots = self.get_positions(account_id)
        patrimony_cad = 0.0
        total_invested_cad = 0.0
        unrealized_pnl_cad = 0.0
        realized_pnl_cad = 0.0

        for lot in lots:
            if account_id is not None:
                qty = lot.quantity_by_account.get(account_id, 0.0)
                if qty <= 0:
                    continue
                weight = (qty / lot.quantity) if lot.quantity else 0.0
            else:
                qty = lot.quantity
                weight = 1.0

            total_invested_cad += qty * lot.avg_cost_cad
            # Realized P&L is a pool-level concept (esp. for the shared
            # non-registered pool) and isn't divisible per sub-account, so
            # the full lot's realized P&L is attributed whenever the filter
            # matches — this is a documented simplification, not a bug.
            realized_pnl_cad += lot.realized_pnl_cad
            if lot.market_value_cad is not None:
                patrimony_cad += lot.market_value_cad * weight
                unrealized_pnl_cad += (lot.unrealized_pnl_cad or 0.0) * weight

        return {
            "patrimony_cad": patrimony_cad,
            "total_invested_cad": total_invested_cad,
            "unrealized_pnl_cad": unrealized_pnl_cad,
            "realized_pnl_cad": realized_pnl_cad,
            # DividendReceived has no account_id in the target schema, so
            # this is always the user-level total regardless of `account_id`.
            "dividends_accum_cad": self._dividends_accum_cad(),
        }

    def _dividends_accum_cad(self) -> float:
        total = 0.0
        rows = DividendReceived.query.filter_by(user_id=self.user_id, confirmed=True).all()
        for row in rows:
            if row.currency == "CAD":
                total += row.total_amount
                continue
            fx_rate = fx_rate_to_cad_today(row.currency)
            if fx_rate is None:
                self.warnings.append(
                    f"dividend for asset {row.asset_id}: no FxRate for {row.currency}->CAD, excluded"
                )
                continue
            total += row.total_amount * fx_rate
        return total

    def quantity_held_as_of(self, asset_id: int, as_of: date) -> float:
        orders = (
            OrderModel.query.filter_by(user_id=self.user_id, asset_id=asset_id)
            .order_by(OrderModel.executed_at.asc())
            .all()
        )
        quantity = 0.0
        for order in orders:
            if order.executed_at.date() > as_of:
                break
            quantity += order.quantity if order.type == OrderType.BUY else -order.quantity
        return quantity

    # -- dividend sync (write) ----------------------------------------------

    def sync_suggested_dividends(self) -> int:
        from src.extensions import db

        asset_ids = {
            row[0]
            for row in OrderModel.query.with_entities(OrderModel.asset_id)
            .filter_by(user_id=self.user_id)
            .distinct()
            .all()
        }
        if not asset_ids:
            return 0

        touched = 0
        for dh in DividendHistory.query.filter(DividendHistory.asset_id.in_(asset_ids)).all():
            pay_date = dh.pay_date or dh.ex_date
            quantity_held = self.quantity_held_as_of(dh.asset_id, dh.ex_date)
            if quantity_held <= 0:
                continue

            existing = DividendReceived.query.filter_by(
                user_id=self.user_id, asset_id=dh.asset_id, pay_date=pay_date
            ).first()
            if existing is not None and (existing.confirmed or existing.dismissed):
                continue

            total_amount = quantity_held * dh.amount
            if existing is None:
                db.session.add(
                    DividendReceived(
                        user_id=self.user_id,
                        asset_id=dh.asset_id,
                        pay_date=pay_date,
                        quantity_held=quantity_held,
                        total_amount=total_amount,
                        currency=dh.currency,
                        confirmed=False,
                    )
                )
            else:
                existing.quantity_held = quantity_held
                existing.total_amount = total_amount
                existing.currency = dh.currency
            touched += 1

        return touched
