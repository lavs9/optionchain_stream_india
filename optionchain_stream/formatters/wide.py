from __future__ import annotations

import logging
from optionchain_stream.models import OptionChainRow

log = logging.getLogger(__name__)

_ZERO = 0.0
_GREEK_KEYS = ("iv", "delta", "theta", "gamma", "vega")


def _extract_greeks(side: dict) -> dict:
    g = side.get("option_greeks") or {}
    return {k: float(g.get(k) or 0.0) for k in _GREEK_KEYS}


def _greeks_missing(side: dict) -> bool:
    return "option_greeks" not in side or not side["option_greeks"]


def _quality_flag(
    ce: dict,
    pe: dict,
    ce_g: dict,
    pe_g: dict,
    prev_row: OptionChainRow | None,
    new_row_fields: dict,
) -> int:
    # flag 1 — zero LTP
    if ce.get("ltp", _ZERO) == _ZERO or pe.get("ltp", _ZERO) == _ZERO:
        return 1

    # flag 2 — Greeks missing or both IV zero
    if _greeks_missing(ce) or _greeks_missing(pe):
        return 2
    if ce_g["iv"] == _ZERO and pe_g["iv"] == _ZERO:
        return 2

    # flag 4 — stale (all price/greek fields identical to previous snapshot)
    if prev_row is not None:
        if _is_stale(prev_row, new_row_fields):
            return 4

    return 0


def _is_stale(prev: OptionChainRow, fields: dict) -> bool:
    stale_keys = (
        "ce_ltp", "ce_bid", "ce_ask", "ce_volume", "ce_oi",
        "ce_iv", "ce_delta", "ce_theta", "ce_gamma", "ce_vega",
        "pe_ltp", "pe_bid", "pe_ask", "pe_volume", "pe_oi",
        "pe_iv", "pe_delta", "pe_theta", "pe_gamma", "pe_vega",
    )
    return all(getattr(prev, k) == fields[k] for k in stale_keys)


def to_wide_rows(
    chain_response: dict,
    underlying: str,
    expiry: str,
    timestamp: int,
    lotsize: int,
    prev_snapshot: dict[float, OptionChainRow] | None = None,
) -> list[OptionChainRow]:
    """Convert broker nested chain dict to flat WIDE rows with quality_flag."""
    rows: list[OptionChainRow] = []

    for strike_data in chain_response.get("strikes", []):
        try:
            strike = float(strike_data.get("strike_price", 0))
            ce = strike_data.get("call_options") or {}
            pe = strike_data.get("put_options") or {}

            ce_g = _extract_greeks(ce)
            pe_g = _extract_greeks(pe)

            fields = dict(
                ce_ltp=float(ce.get("ltp") or 0.0),
                ce_bid=float(ce.get("bid") or 0.0),
                ce_ask=float(ce.get("ask") or 0.0),
                ce_open=float(ce.get("open") or 0.0),
                ce_high=float(ce.get("high") or 0.0),
                ce_low=float(ce.get("low") or 0.0),
                ce_prev_close=float(ce.get("prev_close") or 0.0),
                ce_volume=int(ce.get("volume") or 0),
                ce_oi=int(ce.get("oi") or 0),
                ce_iv=ce_g["iv"], ce_delta=ce_g["delta"],
                ce_theta=ce_g["theta"], ce_gamma=ce_g["gamma"], ce_vega=ce_g["vega"],
                pe_ltp=float(pe.get("ltp") or 0.0),
                pe_bid=float(pe.get("bid") or 0.0),
                pe_ask=float(pe.get("ask") or 0.0),
                pe_open=float(pe.get("open") or 0.0),
                pe_high=float(pe.get("high") or 0.0),
                pe_low=float(pe.get("low") or 0.0),
                pe_prev_close=float(pe.get("prev_close") or 0.0),
                pe_volume=int(pe.get("volume") or 0),
                pe_oi=int(pe.get("oi") or 0),
                pe_iv=pe_g["iv"], pe_delta=pe_g["delta"],
                pe_theta=pe_g["theta"], pe_gamma=pe_g["gamma"], pe_vega=pe_g["vega"],
            )

            prev_row = (prev_snapshot or {}).get(strike)
            flag = _quality_flag(ce, pe, ce_g, pe_g, prev_row, fields)

            row = OptionChainRow(
                timestamp=timestamp,
                underlying=underlying,
                expiry=expiry,
                strike=strike,
                ce_symbol=ce.get("symbol", ""),
                pe_symbol=pe.get("symbol", ""),
                lotsize=lotsize,
                quality_flag=flag,
                **fields,
            )
            rows.append(row)

        except Exception:
            log.exception("Skipping malformed strike in to_wide_rows: %s", strike_data)

    return rows
