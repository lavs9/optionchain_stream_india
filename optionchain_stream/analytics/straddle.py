from __future__ import annotations
import statistics
from optionchain_stream.models import OptionChainRow
from optionchain_stream.analytics.atm import get_atm_strike


def compute_atm_straddle(rows: list[OptionChainRow], spot: float) -> dict:
    """
    Returns ATM straddle metrics for a single (underlying, expiry) slice.

    Keys: atm_strike, straddle_premium, implied_move_pct
    Returns empty dict if rows is empty or spot is zero.
    """
    if not rows or spot == 0:
        return {}
    atm = get_atm_strike(rows, spot)
    if atm is None:
        return {}
    premium = atm.ce_ltp + atm.pe_ltp
    return {
        "atm_strike": atm.strike,
        "straddle_premium": premium,
        "implied_move_pct": premium / spot * 100,
    }


def compute_synthetic_futures(rows: list[OptionChainRow]) -> list[dict]:
    """
    Returns synthetic futures price per strike: ce_ltp - pe_ltp + strike.
    """
    return [
        {"strike": r.strike, "synthetic_fut": r.ce_ltp - r.pe_ltp + r.strike}
        for r in rows
    ]


def compute_synthetic_futures_spread(rows: list[OptionChainRow], spot: float) -> float | None:
    """
    Mean absolute deviation of synthetic_futures from spot across all strikes.
    Large values indicate stale/mis-priced data.
    """
    if not rows:
        return None
    deviations = [abs((r.ce_ltp - r.pe_ltp + r.strike) - spot) for r in rows]
    return statistics.mean(deviations) if deviations else None
