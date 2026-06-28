from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PositionState:
    signal_id: str
    symbol: str
    strategy: str
    entry_time: datetime
    entry_price: float
    stop_loss_pct: float
    trailing_stop_pct: float
    lowest_price: float
    highest_adverse_price: float

