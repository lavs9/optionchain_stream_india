from __future__ import annotations
from optionchain_stream.models import OptionChainRow


def get_atm_strike(rows: list[OptionChainRow], spot: float) -> OptionChainRow | None:
    """Return the row whose strike is closest to spot."""
    if not rows:
        return None
    return min(rows, key=lambda r: abs(r.strike - spot))
