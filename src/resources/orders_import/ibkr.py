import csv
from datetime import datetime

from src.resources.orders_import.base import NormalizedOrderRow, OrderImportStrategy


class IBKRFlexImporter(OrderImportStrategy):
    """Parses the "Trades" section of an IBKR Flex Query CSV export.

    Expected columns (best-effort, based on IBKR's documented Flex Query
    Trades fields; validate against a real export and adjust here if columns
    differ): Symbol, TradeDate, Quantity, TradePrice, IBCommission,
    CurrencyPrimary, Buy/Sell.
    """

    BROKER = "IBKR"

    def parse(self, file_stream) -> list[NormalizedOrderRow]:
        reader = csv.DictReader(file_stream)
        rows = []
        for record in reader:
            side = (record.get("Buy/Sell") or "").strip().upper()
            if side not in ("BUY", "SELL"):
                continue
            rows.append(
                NormalizedOrderRow(
                    symbol=(record.get("Symbol") or "").strip(),
                    type=side,
                    quantity=abs(float(record.get("Quantity") or 0)),
                    price=abs(float(record.get("TradePrice") or 0)),
                    fees=abs(float(record.get("IBCommission") or 0)),
                    currency=(record.get("CurrencyPrimary") or "USD").strip().upper(),
                    executed_at=datetime.strptime((record.get("TradeDate") or "").strip(), "%Y%m%d"),
                    broker=self.BROKER,
                )
            )
        return rows
