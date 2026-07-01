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

import gzip
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

import requests

from optionchain_stream.broker_interface import Broker
from optionchain_stream.instrument_cache import InstrumentCache
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider
from optionchain_stream.instrument_master.upstox_provider import UpstoxInstrumentProvider
from optionchain_stream.models import Tick

log = logging.getLogger(__name__)

_CHAIN_ENDPOINT = "https://api.upstox.com/v2/option/chain"
_CONTRACT_ENDPOINT = "https://api.upstox.com/v2/option/contract"

# Complete instrument master — includes NSE_FO (stock + index option underlyings)
# and BSE instruments, so we can resolve any F&O underlying_symbol → underlying_key.
_INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"

# Canonical instrument_key mapping for common NSE/BSE indices.
# Consulted first (before the downloaded map) so the indices the poller opens
# with resolve instantly without a network round-trip, and so BSE indices
# (SENSEX/BANKEX) — absent from the NSE_FO download — still resolve.
_INSTRUMENT_KEY_MAP: dict[str, str] = {
    "NIFTY":      "NSE_INDEX|Nifty 50",
    "BANKNIFTY":  "NSE_INDEX|Nifty Bank",
    "FINNIFTY":   "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
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

    # Class-level cache of the underlying_symbol → underlying_key map.
    # Shared across instances (the contract/chain master changes at most once
    # a day), with a 1h TTL to pick up new expiries/listings.
    _underlying_key_map: Optional[dict[str, str]] = None
    _underlying_key_cache = InstrumentCache(cache_ttl_seconds=3600)
    _UNDERLYING_KEY_CACHE_KEY = "upstox_underlying_keys"

    def __init__(self, analytics_token: str) -> None:
        self._token = analytics_token
        self._instrument_provider = UpstoxInstrumentProvider()
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {analytics_token}",
            "Accept": "application/json",
        })

    # ── underlying_symbol → underlying_key resolution ──────────────────────

    @classmethod
    def _load_underlying_key_map(cls) -> dict[str, str]:
        """
        Build (and cache) underlying_symbol → underlying_key for every NSE
        F&O underlying, from the Upstox complete instrument master.

        Stock underlyings resolve to "NSE_EQ|<ISIN>" (e.g. AMBER →
        NSE_EQ|INE371P01015); index underlyings resolve to "NSE_INDEX|<name>"
        (e.g. MIDCPNIFTY → NSE_INDEX|NIFTY MID SELECT).  First occurrence wins
        so a given underlying_symbol maps to one stable key.

        Cached two ways: in-memory (class-level) and via InstrumentCache (Redis
        when available, in-memory pickle otherwise) so long-lived pipelines
        don't re-download the ~30MB master every cycle.
        """
        if cls._underlying_key_map is not None:
            return cls._underlying_key_map

        cached = cls._underlying_key_cache.get(cls._UNDERLYING_KEY_CACHE_KEY)
        if cached:
            cls._underlying_key_map = dict(cached)
            return cls._underlying_key_map

        log.info("Downloading Upstox complete instrument master to build underlying_key map…")
        mapping: dict[str, str] = {}
        resp = requests.get(_INSTRUMENTS_URL, timeout=60)
        resp.raise_for_status()
        data = json.loads(gzip.decompress(resp.content))
        for item in data:
            if item.get("segment") != "NSE_FO":
                continue
            sym = item.get("underlying_symbol")
            key = item.get("underlying_key")
            if sym and key and sym not in mapping:
                mapping[sym] = key
        log.info("Built underlying_key map: %d underlyings", len(mapping))
        cls._underlying_key_map = mapping
        try:
            cls._underlying_key_cache.set(
                cls._UNDERLYING_KEY_CACHE_KEY, list(mapping.items())
            )
        except Exception:
            log.warning("Could not persist underlying_key map to InstrumentCache", exc_info=True)
        return mapping

    @classmethod
    def clear_underlying_key_cache(cls) -> None:
        """Drop the in-memory + persisted underlying_key map (re-download on next use)."""
        cls._underlying_key_map = None
        cls._underlying_key_cache.clear(cls._UNDERLYING_KEY_CACHE_KEY)

    def _resolve_instrument_key(self, symbol: str) -> str:
        """
        Resolve an underlying trading symbol (e.g. "AMBER", "MIDCPNIFTY") to the
        instrument_key the /v2/option/* endpoints expect.

        Order:
          1. Static seed (_INSTRUMENT_KEY_MAP) — indices, instant, no network.
          2. Downloaded complete-master map — stocks + extra indices.
          3. Fall back to the raw upper-cased symbol so unmapped underlyings
             still get a deterministic value logged (and a clear 400 upstream).
        """
        up = symbol.upper()
        if up in _INSTRUMENT_KEY_MAP:
            return _INSTRUMENT_KEY_MAP[up]
        try:
            mapping = self._load_underlying_key_map()
        except Exception:
            log.warning("underlying_key map download failed — falling back to raw symbol")
            return up
        if up in mapping:
            return mapping[up]
        log.warning("underlying %r not in instrument master — passing raw symbol", symbol)
        return up

    # ── rate-limited HTTP ────────────────────────────────────────────────────

    def _request(self, url: str, params: dict, timeout: int = 10, max_retries: int = 3):
        """
        GET with 429 / Retry-After backoff.

        With ~215 underlyings × all expiries (≈900 calls / polling cycle) the
        2,000-req/30-min ceiling is within reach; a 429 must make the broker
        self-throttle rather than fail the whole poll cycle.
        """
        last_resp = None
        for attempt in range(max_retries + 1):
            resp = self._session.get(url, params=params, timeout=timeout)
            last_resp = resp
            if resp.status_code == 429 and attempt < max_retries:
                retry_after = resp.headers.get("Retry-After", "5")
                try:
                    wait = int(float(retry_after))
                except (TypeError, ValueError):
                    wait = 5
                log.warning(
                    "Upstox 429 for %s — backing off %ds (attempt %d/%d)",
                    params.get("instrument_key"), wait, attempt + 1, max_retries,
                )
                time.sleep(wait)
                continue
            return resp
        return last_resp

    # ── Broker ABC — required methods ────────────────────────────────────────

    def authenticate(self) -> None:
        """No-op: analytics token is pre-authenticated at construction time."""
        pass

    def get_instrument_provider(self) -> InstrumentProvider:
        return self._instrument_provider

    def fetch_option_contracts(self, symbol: str) -> list[str]:
        """
        Return sorted ISO expiry strings (YYYY-MM-DD) available for the underlying
        via GET /v2/option/contract.

        The poller normally derives expiries from the cached instrument master
        (no API cost); this method is here for callers that want expiries
        straight from the Upstox option-contracts endpoint.
        """
        instrument_key = self._resolve_instrument_key(symbol)
        try:
            resp = self._request(
                _CONTRACT_ENDPOINT,
                params={"instrument_key": instrument_key},
            )
            resp.raise_for_status()
            data = resp.json().get("data") or []
            seen: set[str] = {d.get("expiry") for d in data if d.get("expiry")}
            return sorted(seen)
        except Exception:
            log.exception("Upstox analytics contract fetch failed %s", symbol)
            return []

    def fetch_option_chain(self, symbol: str, expiry: str) -> dict:
        """
        Fetch option chain via Upstox Analytics Token.

        Args:
            symbol: Underlying trading symbol, e.g. "NIFTY", "BANKNIFTY",
                    "AMBER", "RELIANCE".  Resolved to the instrument_key the
                    /v2/option/chain endpoint expects (e.g. AMBER →
                    NSE_EQ|INE371P01015; MIDCPNIFTY → NSE_INDEX|NIFTY MID SELECT).
            expiry: Expiry date in YYYY-MM-DD format, e.g. "2026-05-29".

        Returns:
            Normalized chain dict with shape { spot_price, strikes: [...] }
            compatible with to_wide_rows().

        Note:
            open/high/low fields will be 0 — the /v2/option/chain endpoint
            does not return intraday OHLC for individual strikes.
        """
        instrument_key = self._resolve_instrument_key(symbol)
        try:
            resp = self._request(
                _CHAIN_ENDPOINT,
                params={"instrument_key": instrument_key, "expiry_date": expiry},
            )
            resp.raise_for_status()
            return _normalize_chain(resp.json())
        except requests.HTTPError as exc:
            log.error("Upstox analytics chain HTTP error %s %s (%s): %s",
                     symbol, expiry, instrument_key, exc)
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
