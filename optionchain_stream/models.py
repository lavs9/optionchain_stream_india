from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Instrument:
    exchange: str
    token: str  # Changed to str to support alphanumeric tokens (e.g. Upstox)
    symbol: str  # Standardized symbol e.g., NIFTY23OCT19500CE
    name: str    # Underlying name e.g., NIFTY
    expiry: datetime
    strike: float
    lot_size: int
    instrument_type: str # CE/PE/FUT/EQ
    broker_token: str # Broker specific token
    tick_size: float

@dataclass
class Tick:
    token: str # Changed to str
    timestamp: datetime
    last_price: float
    volume: int
    oi: int
    change: float
    bid_price: Optional[float] = 0.0
    ask_price: Optional[float] = 0.0
    bid_qty: Optional[int] = 0
    ask_qty: Optional[int] = 0
