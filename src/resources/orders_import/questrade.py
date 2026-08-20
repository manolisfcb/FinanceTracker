import csv
from datetime import datetime

from src.resources.orders_import.base import NormalizedOrderRow, OrderImportStrategy

_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y")


def _parse_date(value: str) -> datetime:
    value = value.strip()
    candidate = value[:19] if "T" in value else value
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized Questrade date format: {value!r}")


class QuestradeCSVImporter(OrderImportStrategy):
    """Parses a Questrade "Account Activity" CSV export.

    Expected columns (best-effort, based on Questrade's documented export
    format — validate against a real export and adjust here if columns
    differ): Transaction Date, Action, Symbol, Quantity, Price, Commission,
    Currency. Rows whose Action isn't Buy/Sell (dividends, transfers,
    interest, ...) are skipped.
    """

    BROKER = "Questrade"

    def parse(self, file_stream) -> list[NormalizedOrderRow]:
        reader = csv.DictReader(file_stream)
        rows = []
        for record in reader:
            action = (record.get("Action") or "").strip().upper()
            if action not in ("BUY", "SELL"):
                continue
            rows.append(
                NormalizedOrderRow(
                    symbol=(record.get("Symbol") or "").strip(),
                    type=action,
                    quantity=abs(float(record.get("Quantity") or 0)),
                    price=abs(float(record.get("Price") or 0)),
                    fees=abs(float(record.get("Commission") or 0)),
                    currency=(record.get("Currency") or "CAD").strip().upper(),
                    executed_at=_parse_date(record.get("Transaction Date") or record.get("Settlement Date")),
                    broker=self.BROKER,
                )
            )
        return rows
