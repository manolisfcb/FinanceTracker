import csv
from datetime import datetime

from src.resources.orders_import.base import NormalizedOrderRow, OrderImportStrategy


class WealthsimpleCSVImporter(OrderImportStrategy):
    """Parses a Wealthsimple Trade/Managed activity CSV export.

    Expected columns (best-effort — Wealthsimple does not publish a fixed
    export schema; validate against a real export and adjust here if columns
    differ): Date, Transaction Type, Symbol, Quantity, Price, Amount,
    Currency. Rows whose Transaction Type isn't Buy/Sell (dividends,
    deposits, ...) are skipped.
    """

    BROKER = "Wealthsimple"

    def parse(self, file_stream) -> list[NormalizedOrderRow]:
        reader = csv.DictReader(file_stream)
        rows = []
        for record in reader:
            txn_type = (record.get("Transaction Type") or "").strip().upper()
            if txn_type not in ("BUY", "SELL"):
                continue
            price = abs(float(record.get("Price") or 0))
            quantity = abs(float(record.get("Quantity") or 0))
            amount = abs(float(record.get("Amount") or 0))
            fees = max(0.0, abs(amount - quantity * price)) if quantity and price else 0.0
            rows.append(
                NormalizedOrderRow(
                    symbol=(record.get("Symbol") or "").strip(),
                    type=txn_type,
                    quantity=quantity,
                    price=price,
                    fees=fees,
                    currency=(record.get("Currency") or "CAD").strip().upper(),
                    executed_at=datetime.strptime((record.get("Date") or "").strip(), "%Y-%m-%d"),
                    broker=self.BROKER,
                )
            )
        return rows
