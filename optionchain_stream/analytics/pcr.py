from __future__ import annotations
from optionchain_stream.models import OptionChainRow


def compute_oi_zones(rows: list[OptionChainRow], top_n: int = 3) -> dict:
    """
    Identify top OI concentration strikes as support/resistance zones.

    Returns:
        resistance_strikes: list[float]  — top CE OI strikes (call walls)
        support_strikes:    list[float]  — top PE OI strikes (put walls)
        chain_pcr:          float        — total pe_oi / total ce_oi
    """
    if not rows:
        return {"resistance_strikes": [], "support_strikes": [], "chain_pcr": 0.0}

    sorted_by_ce = sorted(rows, key=lambda r: r.ce_oi, reverse=True)
    sorted_by_pe = sorted(rows, key=lambda r: r.pe_oi, reverse=True)

    total_ce = sum(r.ce_oi for r in rows)
    total_pe = sum(r.pe_oi for r in rows)
    chain_pcr = total_pe / total_ce if total_ce > 0 else 0.0

    return {
        "resistance_strikes": [r.strike for r in sorted_by_ce[:top_n]],
        "support_strikes":    [r.strike for r in sorted_by_pe[:top_n]],
        "chain_pcr":          chain_pcr,
    }
