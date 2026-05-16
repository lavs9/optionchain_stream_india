from __future__ import annotations
from optionchain_stream.models import OptionChainRow


def compute_max_pain(rows: list[OptionChainRow]) -> float | None:
    """
    Compute the max pain strike: the settlement price at which option holders
    (buyers) face maximum aggregate loss (i.e. sellers face minimum payout).

    For each candidate settlement price S (= each strike):
      pain(S) = sum_K [ max(0, K-S)*ce_oi*lotsize + max(0, S-K)*pe_oi*lotsize ]
    Returns the S that minimises pain, or None if rows is empty.
    """
    if not rows:
        return None

    strikes = [r.strike for r in rows]
    min_pain = float("inf")
    max_pain_strike = strikes[0]

    for s in strikes:
        pain = sum(
            max(0.0, r.strike - s) * r.ce_oi * r.lotsize
            + max(0.0, s - r.strike) * r.pe_oi * r.lotsize
            for r in rows
        )
        if pain < min_pain:
            min_pain = pain
            max_pain_strike = s

    return max_pain_strike
