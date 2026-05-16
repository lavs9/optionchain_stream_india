from __future__ import annotations

import logging
from datetime import date, datetime
from optionchain_stream.models import OptionChainRow

log = logging.getLogger(__name__)

_ZERO = 0.0
_GREEK_KEYS = ("iv", "delta", "theta", "gamma", "vega")
_ATM_THRESHOLD = 0.002  # within 0.2% of spot counts as ATM


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


def _parse_expiry_date(expiry_str: str) -> date | None:
    """Parse broker expiry strings like '29MAY26' or '2026-05-29'."""
    for fmt in ("%d%b%y", "%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(expiry_str.upper(), fmt).date()
        except ValueError:
            continue
    return None


def _moneyness(strike: float, spot: float) -> str:
    if spot == 0:
        return ""
    if abs(strike - spot) / spot <= _ATM_THRESHOLD:
        return "ATM"
    return "ITM" if strike < spot else "OTM"


def to_wide_rows(
    chain_response: dict,
    underlying: str,
    expiry: str,
    timestamp: int,
    lotsize: int,
    prev_snapshot: dict[float, OptionChainRow] | None = None,
) -> list[OptionChainRow]:
    """Convert broker nested chain dict to flat WIDE rows with quality_flag and analytics."""
    rows: list[OptionChainRow] = []

    spot = float(chain_response.get("spot_price") or 0.0)
    today = date.fromtimestamp(timestamp)
    expiry_date = _parse_expiry_date(expiry)

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

            ce_ltp = fields["ce_ltp"]
            pe_ltp = fields["pe_ltp"]
            ce_oi  = fields["ce_oi"]
            pe_oi  = fields["pe_oi"]

            # tianjin-7nm: moneyness enrichment
            moneyness = _moneyness(strike, spot)
            distance_from_spot_pct = (strike - spot) / spot * 100 if spot != 0 else 0.0
            dte = (expiry_date - today).days if expiry_date is not None else 0
            ce_intrinsic = max(0.0, spot - strike)
            pe_intrinsic = max(0.0, strike - spot)
            ce_time_value = max(0.0, ce_ltp - ce_intrinsic)
            pe_time_value = max(0.0, pe_ltp - pe_intrinsic)

            # tianjin-1da: synthetic futures (ce - pe + strike ≈ forward price)
            synthetic_futures = ce_ltp - pe_ltp + strike

            # tianjin-6to: GEX — skip when Greeks are missing (quality_flag == 2)
            if flag != 2 and spot != 0:
                ce_gex = ce_g["gamma"] * ce_oi * lotsize * spot
                pe_gex = pe_g["gamma"] * pe_oi * lotsize * spot
                net_gex = pe_gex - ce_gex
            else:
                ce_gex = pe_gex = net_gex = 0.0

            # tianjin-6r0: per-strike PCR
            strike_pcr = pe_oi / ce_oi if ce_oi > 0 else None

            # tianjin-bjh: delta OI vs previous cycle
            if prev_row is not None:
                ce_oi_change = ce_oi - prev_row.ce_oi
                pe_oi_change = pe_oi - prev_row.pe_oi
            else:
                ce_oi_change = pe_oi_change = 0

            row = OptionChainRow(
                timestamp=timestamp,
                underlying=underlying,
                expiry=expiry,
                strike=strike,
                ce_symbol=ce.get("symbol", ""),
                pe_symbol=pe.get("symbol", ""),
                lotsize=lotsize,
                quality_flag=flag,
                moneyness=moneyness,
                distance_from_spot_pct=distance_from_spot_pct,
                days_to_expiry=dte,
                ce_intrinsic=ce_intrinsic,
                pe_intrinsic=pe_intrinsic,
                ce_time_value=ce_time_value,
                pe_time_value=pe_time_value,
                synthetic_futures=synthetic_futures,
                ce_gex=ce_gex,
                pe_gex=pe_gex,
                net_gex=net_gex,
                strike_pcr=strike_pcr,
                ce_oi_change=ce_oi_change,
                pe_oi_change=pe_oi_change,
                **fields,
            )
            rows.append(row)

        except Exception:
            log.exception("Skipping malformed strike in to_wide_rows: %s", strike_data)

    return rows
