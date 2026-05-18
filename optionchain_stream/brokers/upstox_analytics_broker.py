"""
UpstoxAnalyticsBroker
=====================
Uses Upstox's long-lived Analytics Token (1-year validity, no OAuth flow) to
fetch option chain data via the public REST API.

Analytics tokens are read-only — streaming, subscription, and trading methods
are not available.  The token is generated once from the Upstox Developer Apps
dashboard (Analytics tab) and stored in config as ``analytics_token``.

API reference:
  https://upstox.com/developer/api-documentation/analytics-token/
  https://upstox.com/developer/api-documentation/get-pc-option-chain/

Supported APIs (via Analytics Token):
  PUT/CALL option chain  — GET /v2/option/chain
  Option contracts       — GET /v2/option/contract
  Market quotes (full)   — GET /v2/market-quote/quotes
  OHLC v3 / LTP v3       — GET /v3/market-quote/...
  Historical candles v3  — GET /v3/historical-candle/...
  Instrument search      — GET /v2/instruments/search
  Exchange status, margin details, option Greeks calculator
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

import requests

from optionchain_stream.broker_interface import Broker
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider
from optionchain_stream.instrument_master.upstox_provider import UpstoxInstrumentProvider
from optionchain_stream.models import Tick

log = logging.getLogger(__name__)

_CHAIN_ENDPOINT = "https://api.upstox.com/v2/option/chain"

# Canonical instrument_key mapping for common NSE/BSE indices.
# Passed as the `instrument_key` query param to the option chain endpoint.
_INSTRUMENT_KEY_MAP: dict[str, str] = {
    "NIFTY":      "NSE_INDEX|Nifty 50",
    "BANKNIFTY":  "NSE_INDEX|Nifty Bank",
    "FINNIFTY":   "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY": "NSE_INDEX|Nifty Mid Select",
    "SENSEX":     "BSE_INDEX|SENSEX",
    "BANKEX":     "BSE_INDEX|BANKEX",
}


def _normalize_chain(raw: dict) -> dict:
    """
    Convert the raw Upstox /v2/option/chain response into the normalized
    wire format consumed by to_wide_rows().

    Upstox response shape (per strike):
      {
        "underlying_spot_price": 22976.2,
        "strike_price": 21100,
        "call_options": {
          "instrument_key": "NSE_FO|51059",
          "market_data": { ltp, volume, oi, close_price, bid_price, ask_price, ... },
          "option_greeks": { iv, delta, gamma, theta, vega, pop }
        },
        "put_options": { ... }
      }

    Normalized output (to_wide_rows() wire format):
      {
        "spot_price": float,
        "strikes": [
          {
            "strike_price": float,
            "call_options": { symbol, ltp, bid, ask, open, high, low, prev_close,
                              volume, oi, option_greeks: {iv, delta, gamma, theta, vega} },
            "put_options": { ... }
          }, ...
        ]
      }
    """
    data: list[dict] = raw.get("data") or []
    if not data:
        return {"spot_price": 0.0, "strikes": []}

    spot_price = float(data[0].get("underlying_spot_price") or 0.0)

    def _norm_side(side: dict) -> dict:
        md = side.get("market_data") or {}
        g  = side.get("option_greeks") or {}
        return {
            "symbol":     side.get("instrument_key", ""),
            "ltp":        float(md.get("ltp")         or 0.0),
            "bid":        float(md.get("bid_price")    or 0.0),
            "ask":        float(md.get("ask_price")    or 0.0),
            "open":       0.0,   # not returned by this endpoint
            "high":       0.0,
            "low":        0.0,
            "prev_close": float(md.get("close_price")  or 0.0),
            "volume":     int(md.get("volume")          or 0),
            "oi":         int(md.get("oi")              or 0),
            "option_greeks": {
                "iv":    float(g.get("iv")    or 0.0),
                "delta": float(g.get("delta") or 0.0),
                "gamma": float(g.get("gamma") or 0.0),
                "theta": float(g.get("theta") or 0.0),
                "vega":  float(g.get("vega")  or 0.0),
            },
        }

    strikes = [
        {
            "strike_price":  float(item.get("strike_price") or 0.0),
            "call_options":  _norm_side(item.get("call_options") or {}),
            "put_options":   _norm_side(item.get("put_options")  or {}),
        }
        for item in data
    ]
    return {"spot_price": spot_price, "strikes": strikes}


class UpstoxAnalyticsBroker(Broker):
    """
    Read-only Upstox broker authenticated with a long-lived Analytics Token.

    Usage::

        broker = UpstoxAnalyticsBroker(analytics_token="eyJ...")
        chain  = broker.fetch_option_chain("NIFTY", "2026-05-29")

    Or via BrokerCoordinator.from_config::

        coordinator = BrokerCoordinator.from_config({
            "broker": "upstox",
            "analytics_token": "eyJ...",   # triggers analytics mode automatically
        })

    Token generation:
        Upstox Developer Apps → Analytics tab → Generate Token
        (https://account.upstox.com/developer/apps#analytics)
        Token is valid for 1 year; only one token active per account.

    Limitations:
        - No trading (orders, positions, holdings)
        - No real-time streaming / WebSocket
        - subscribe(), on_tick(), connect() raise NotImplementedError
        - open/high/low fields are 0 (not returned by the option chain endpoint)
    """

    def __init__(self, analytics_token: str) -> None:
        self._token = analytics_token
        self._instrument_provider = UpstoxInstrumentProvider()
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {analytics_token}",
            "Accept": "application/json",
        })

    # ── Broker ABC — required methods ────────────────────────────────────────

    def authenticate(self) -> None:
        """No-op: analytics token is pre-authenticated at construction time."""
        pass

    def get_instrument_provider(self) -> InstrumentProvider:
        return self._instrument_provider

    def fetch_option_chain(self, symbol: str, expiry: str) -> dict:
        """
        Fetch option chain via Upstox Analytics Token.

        Args:
            symbol: Underlying name, e.g. "NIFTY", "BANKNIFTY".
            expiry: Expiry date in YYYY-MM-DD format, e.g. "2026-05-29".

        Returns:
            Normalized chain dict with shape { spot_price, strikes: [...] }
            compatible with to_wide_rows().

        Note:
            open/high/low fields will be 0 — the /v2/option/chain endpoint
            does not return intraday OHLC for individual strikes.
        """
        instrument_key = _INSTRUMENT_KEY_MAP.get(symbol.upper(), symbol)
        try:
            resp = self._session.get(
                _CHAIN_ENDPOINT,
                params={"instrument_key": instrument_key, "expiry_date": expiry},
                timeout=10,
            )
            resp.raise_for_status()
            return _normalize_chain(resp.json())
        except requests.HTTPError as exc:
            log.error("Upstox analytics chain HTTP error %s %s: %s", symbol, expiry, exc)
            return {"spot_price": 0.0, "strikes": []}
        except Exception as exc:
            log.exception("Upstox analytics chain fetch failed %s %s", symbol, expiry)
            return {"spot_price": 0.0, "strikes": []}

    # ── Streaming methods — not available with analytics token ────────────────

    def subscribe(self, tokens: List[str], mode: str = "full") -> None:
        raise NotImplementedError(
            "UpstoxAnalyticsBroker is read-only. "
            "Use UpstoxBroker (OAuth) for real-time streaming."
        )

    def on_tick(self, callback: Callable[[List[Tick]], None]) -> None:
        raise NotImplementedError(
            "UpstoxAnalyticsBroker is read-only. "
            "Use UpstoxBroker (OAuth) for real-time streaming."
        )

    def connect(self) -> None:
        raise NotImplementedError(
            "UpstoxAnalyticsBroker is read-only. "
            "Use UpstoxBroker (OAuth) for real-time streaming."
        )
