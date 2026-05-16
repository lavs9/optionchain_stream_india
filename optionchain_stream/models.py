from __future__ import annotations
from dataclasses import dataclass, field
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


@dataclass
class OptionChainRow:
    """One row per strike in WIDE format — CE and PE side by side."""
    timestamp:     int
    underlying:    str
    expiry:        str
    strike:        float
    ce_symbol:     str
    ce_ltp:        float
    ce_bid:        float
    ce_ask:        float
    ce_open:       float
    ce_high:       float
    ce_low:        float
    ce_prev_close: float
    ce_volume:     int
    ce_oi:         int
    ce_iv:         float
    ce_delta:      float
    ce_theta:      float
    ce_gamma:      float
    ce_vega:       float
    pe_symbol:     str
    pe_ltp:        float
    pe_bid:        float
    pe_ask:        float
    pe_open:       float
    pe_high:       float
    pe_low:        float
    pe_prev_close: float
    pe_volume:     int
    pe_oi:         int
    pe_iv:         float
    pe_delta:      float
    pe_theta:      float
    pe_gamma:      float
    pe_vega:       float
    lotsize:       int
    quality_flag:  int  # 0=clean 1=zero_ltp 2=missing_greeks 3=gap 4=stale
    # tianjin-7nm: moneyness / strike enrichment
    moneyness:              str   = ""     # ITM/ATM/OTM from CE perspective
    distance_from_spot_pct: float = 0.0   # (strike - spot) / spot * 100
    days_to_expiry:         int   = 0
    ce_intrinsic:           float = 0.0
    pe_intrinsic:           float = 0.0
    ce_time_value:          float = 0.0
    pe_time_value:          float = 0.0
    # tianjin-1da: synthetic futures
    synthetic_futures:      float = 0.0   # ce_ltp - pe_ltp + strike
    # tianjin-6to: gamma exposure per strike
    ce_gex:  float = 0.0
    pe_gex:  float = 0.0
    net_gex: float = 0.0
    # tianjin-6r0: per-strike PCR
    strike_pcr: Optional[float] = None
    # tianjin-bjh: delta OI per cycle
    ce_oi_change: int = 0
    pe_oi_change: int = 0


@dataclass
class CycleHealth:
    """Stats for one fetch cycle — returned to caller, never stored internally."""
    ts:               int
    cycle_type:       str
    symbols_expected: int
    symbols_received: int
    gaps:             int
    stale_warnings:   int
    duration_ms:      int
    error:            str | None
    # tianjin-1da: chain-level straddle metrics (keyed by (underlying, expiry))
    atm_straddle_premium:     Optional[float] = None
    synthetic_futures_spread: Optional[float] = None
    # tianjin-6to: GEX flip strike (keyed by (underlying, expiry))
    gex_flip_strike: Optional[float] = None
    # tianjin-6r0: OI concentration zones (keyed by (underlying, expiry))
    oi_zones: Optional[dict] = None
    # tianjin-7q0: max pain strike (keyed by (underlying, expiry))
    max_pain_strike: Optional[float] = None
