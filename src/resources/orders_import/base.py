import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class NormalizedOrderRow:
    symbol: str
    type: str  # 'BUY' | 'SELL'
    quantity: float
    price: float
    fees: float
    currency: str
    executed_at: datetime
    broker: str

    def import_hash(self) -> str:
        raw = f"{self.executed_at.isoformat()}|{self.symbol}|{self.type}|{self.quantity}|{self.price}|{self.broker}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class OrderImportStrategy(ABC):
    @abstractmethod
    def parse(self, file_stream) -> list[NormalizedOrderRow]:
        """Parse a broker's CSV export into normalized order rows.

        `file_stream` is a text-mode iterable of lines (e.g. a werkzeug
        FileStorage decoded, or an open text file in tests).
        """
