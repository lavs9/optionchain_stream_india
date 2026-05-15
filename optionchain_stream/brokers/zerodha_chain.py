from __future__ import annotations

import csv
import datetime
import io
import logging
import math
import time

import requests

log = logging.getLogger(__name__)

_INSTRUMENTS_URL = "https://api.kite.trade/instruments"
_RISK_FREE_RATE = 0.065
_SPOT_SYMBOL = "NSE:NIFTY 50"
_SPOT_SYMBOLS = {
    "NIFTY": "NSE:NIFTY 50",
    "BANKNIFTY": "NSE:NIFTY BANK",
    "FINNIFTY": "NSE:NIFTY FIN SERVICE",
    "MIDCPNIFTY": "NSE:NIFTY MID SELECT",
    "SENSEX": "BSE:SENSEX",
}
_BATCH_SIZE = 1000


def _time_to_expiry(expiry_str: str) -> float:
    """Years to expiry. Minimum 1 day to avoid division-by-zero."""
    expiry = datetime.date.fromisoformat(expiry_str)
    days = max((expiry - datetime.date.today()).days, 1)
    return days / 365.0


def _compute_greeks(ltp: float, spot: float, strike: float, t: float, flag: str) -> dict:
    """Black-76 Greeks via py_vollib. Returns zeros on failure (flag=2 will be set upstream)."""
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from py_vollib.black.implied_volatility import implied_volatility
            from py_vollib.black.greeks.analytical import delta, gamma, theta, vega

        F = spot
        r = _RISK_FREE_RATE
        iv = implied_volatility(ltp, F, strike, t, r, flag)
        return {
            "iv": float(iv),
            "delta": float(delta(flag, F, strike, t, r, iv)),
            "gamma": float(gamma(flag, F, strike, t, r, iv)),
            "theta": float(theta(flag, F, strike, t, r, iv)),
            "vega": float(vega(flag, F, strike, t, r, iv)),
        }
    except Exception:
        log.debug("Greek computation failed for strike=%s flag=%s ltp=%s", strike, flag, ltp)
        return {"iv": 0.0, "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}


def _parse_depth(depth: dict, side: str) -> float:
    levels = depth.get(side, [])
    return float(levels[0]["price"]) if levels else 0.0


class ZerodhaChainFetcher:
    """
    Reconstructs option chain for Zerodha via batch kite.quote() calls.
    Greeks are computed locally via Black-76 (not broker-native).
    Output shape matches Upstox fetch_option_chain() — to_wide_rows() handles both.
    """

    def __init__(self, kite_client, instrument_cache_dir: str = "/tmp"):
        self._kite = kite_client
        self._cache_dir = instrument_cache_dir
        self._instrument_csv: str | None = None  # override in tests

    def refresh_instrument_master(self) -> None:
        """Download and cache Zerodha instrument CSV. Call once at startup or weekly."""
        resp = requests.get(_INSTRUMENTS_URL, timeout=30)
        resp.raise_for_status()
        self._instrument_csv = resp.text
        log.info("Zerodha instrument master refreshed (%d bytes)", len(self._instrument_csv))

    def _get_csv(self) -> str:
        if self._instrument_csv is None:
            self.refresh_instrument_master()
        return self._instrument_csv

    def _filter_instruments(self, underlying: str, expiry: str) -> list[dict]:
        """Return all CE+PE rows for given underlying and expiry date."""
        reader = csv.DictReader(io.StringIO(self._get_csv()))
        return [
            r for r in reader
            if r.get("name") == underlying
            and r.get("instrument_type") in ("CE", "PE")
            and r.get("expiry") == expiry
        ]

    def _fetch_quotes(self, instruments: list[dict]) -> dict:
        """Batch kite.quote() in chunks of _BATCH_SIZE. Returns merged quote dict."""
        nfo_symbols = [f"NFO:{r['tradingsymbol']}" for r in instruments]
        merged: dict = {}
        for i in range(0, len(nfo_symbols), _BATCH_SIZE):
            batch = nfo_symbols[i: i + _BATCH_SIZE]
            try:
                merged.update(self._kite.quote(batch))
            except Exception:
                log.exception("kite.quote() batch %d failed", i // _BATCH_SIZE)
            if i + _BATCH_SIZE < len(nfo_symbols):
                time.sleep(1)  # 1 req/sec hard limit
        return merged

    def _get_spot(self, underlying: str) -> float:
        spot_sym = _SPOT_SYMBOLS.get(underlying, f"NSE:{underlying}")
        try:
            q = self._kite.quote([spot_sym])
            return float(q[spot_sym]["last_price"])
        except Exception:
            log.warning("Could not fetch spot for %s", underlying)
            return 0.0

    def fetch_chain(self, underlying: str, expiry: str) -> dict:
        """
        Fetch and reconstruct option chain. Returns broker-normalized nested dict.
        Same shape as Upstox fetch_option_chain() output.

        Args:
            underlying: e.g. "NIFTY"
            expiry:     ISO date string e.g. "2026-05-19"
        """
        instruments = self._filter_instruments(underlying, expiry)
        if not instruments:
            log.warning("No instruments found for %s %s", underlying, expiry)
            return {"spot_price": 0.0, "strikes": []}

        quotes = self._fetch_quotes(instruments)
        spot = self._get_spot(underlying)
        t = _time_to_expiry(expiry)

        # Group by strike
        by_strike: dict[float, dict] = {}
        for row in instruments:
            strike = float(row["strike"])
            itype = row["instrument_type"]  # CE or PE
            sym = row["tradingsymbol"]
            nfo_key = f"NFO:{sym}"
            q = quotes.get(nfo_key, {})

            ohlc = q.get("ohlc", {})
            depth = q.get("depth", {})
            ltp = float(q.get("last_price") or 0.0)
            bid = _parse_depth(depth, "buy")
            ask = _parse_depth(depth, "sell")

            greeks = _compute_greeks(ltp, spot, strike, t, itype[0].lower())

            side_data = {
                "symbol": sym,
                "ltp": ltp,
                "bid": bid,
                "ask": ask,
                "open": float(ohlc.get("open") or 0.0),
                "high": float(ohlc.get("high") or 0.0),
                "low": float(ohlc.get("low") or 0.0),
                "prev_close": float(ohlc.get("close") or 0.0),
                "volume": int(q.get("volume") or 0),
                "oi": int(q.get("oi") or 0),
                "option_greeks": greeks,
            }

            if strike not in by_strike:
                by_strike[strike] = {}
            by_strike[strike]["CE" if itype == "CE" else "PE"] = side_data

        strikes = []
        for strike in sorted(by_strike):
            sides = by_strike[strike]
            strikes.append({
                "strike_price": strike,
                "call_options": sides.get("CE", {}),
                "put_options": sides.get("PE", {}),
            })

        return {"spot_price": spot, "strikes": strikes}
