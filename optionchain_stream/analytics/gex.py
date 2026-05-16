from __future__ import annotations
from optionchain_stream.models import OptionChainRow


def compute_gex_flip(rows: list[OptionChainRow], spot_price: float) -> float | None:
    """
    Find the strike where cumulative net GEX changes sign (vol regime boundary).
    Rows must already have net_gex populated. Returns None if no flip found.
    """
    if not rows:
        return None
    sorted_rows = sorted(rows, key=lambda r: r.strike)
    cumulative = 0.0
    prev_strike = None
    for row in sorted_rows:
        prev_sign = cumulative >= 0
        cumulative += row.net_gex
        curr_sign = cumulative >= 0
        if prev_strike is not None and prev_sign != curr_sign:
            return row.strike
        prev_strike = row.strike
    return None
