"""Dhan broker adapter (Broker interface) on dhanhq 2.3.0 + the v2 market feed client.

Streaming uses optionchain_stream.dhan.feed.DhanMarketFeed (connection split, paced
subscribe, reconnect + resubscribe, stall watchdog) and ChainAssembler for state. This class
never logs in: pass an access token, or a `token_provider` that returns the current one.

For the chain-snapshot API (what Findia uses) see optionchain_stream.dhan: build a Universe,
run DhanMarketFeed with ChainAssembler.on_packet, and a MinuteSnapshotter.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import logging
from typing import Any, Callable, Dict, List, Optional

from optionchain_stream.broker_interface import Broker
from optionchain_stream.chain_state import ChainAssembler, ContractMeta
from optionchain_stream.dhan import packets as P
from optionchain_stream.dhan.feed import DhanMarketFeed, FeedInstrument
from optionchain_stream.instrument_master.dhan_provider import DhanInstrumentProvider
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider
from optionchain_stream.models import Tick

log = logging.getLogger(__name__)


class DhanBroker(Broker):
    def __init__(self, client_id: str, access_token: Optional[str] = None, *,
                 token_provider: Optional[Callable[[], Optional[str]]] = None,
                 instrument_provider: Optional[DhanInstrumentProvider] = None,
                 feed_options: Optional[dict] = None):
        if access_token is None and token_provider is None:
            raise ValueError("pass access_token or token_provider")
        self.client_id = client_id
        self._token_provider = token_provider or (lambda: access_token)
        self.instrument_provider = instrument_provider or DhanInstrumentProvider()
        self.feed_options = dict(feed_options or {})
        self.callbacks: List[Callable[[List[Tick]], None]] = []
        self._instruments: Dict[tuple, FeedInstrument] = {}
        self._metas: Dict[tuple, ContractMeta] = {}
        self.feed: Optional[DhanMarketFeed] = None
        self.assembler: Optional[ChainAssembler] = None
        self._dhan = None

    def authenticate(self):
        """No-op: this adapter never logs in (Dhan allows one token per account)."""

    def get_instrument_provider(self) -> InstrumentProvider:
        return self.instrument_provider

    def subscribe(self, tokens: List[str], mode: str = ""):
        """Queue instruments (Dhan security ids) for the next connect(). mode: "" (default per
        segment: index=ticker, BSE_FNO=quote, else full) | "ticker" | "quote" | "full"."""
        for token in tokens:
            inst = self.instrument_provider.get_instrument_by_token(str(token))
            if inst is None:
                log.warning("Dhan token %s not in the scrip master; skipped", token)
                continue
            seg = P.SEGMENT_CODES.get(inst.exchange)
            if seg is None:
                log.warning("Dhan token %s: unknown segment %s; skipped", token, inst.exchange)
                continue
            key = (seg, int(inst.token))
            self._instruments[key] = FeedInstrument(seg, key[1], mode if mode in
                                                    ("ticker", "quote", "full") else "")
            self._metas[key] = ContractMeta(
                seg, key[1], inst.name, inst.instrument_type,
                inst.expiry.date() if inst.expiry else None, inst.strike, inst.symbol,
                inst.lot_size)

    def on_tick(self, callback: Callable[[List[Tick]], None]):
        self.callbacks.append(callback)

    def _on_packet(self, pkt, shard: int) -> None:
        self.assembler.on_packet(pkt, shard)
        if not isinstance(pkt, (P.TickerPacket, P.QuotePacket, P.FullPacket, P.OIPacket)):
            return
        leg = self.assembler.leg(*pkt.key)
        if leg is None or leg.ltp is None:
            return
        ts = leg.last_trade_utc or _dt.datetime.now(_dt.timezone.utc)
        tick = Tick(
            token=str(pkt.security_id), timestamp=ts, last_price=float(leg.ltp),
            volume=int(leg.volume or 0), oi=int(leg.oi or 0),
            change=(leg.ltp - leg.prev_close) if leg.prev_close else 0.0,
            bid_price=leg.bid or 0.0, ask_price=leg.ask or 0.0,
            bid_qty=leg.bid_qty or 0, ask_qty=leg.ask_qty or 0)
        for cb in self.callbacks:
            cb([tick])

    def build_feed(self) -> DhanMarketFeed:
        self.assembler = ChainAssembler(self._metas.values())
        self.feed = DhanMarketFeed(self.client_id, self._token_provider,
                                   self._instruments.values(), on_packet=self._on_packet,
                                   **self.feed_options)
        return self.feed

    def connect(self):
        """Blocking: run the feed until stop() (like the other brokers' connect())."""
        feed = self.build_feed()
        asyncio.run(feed.run())

    def stop(self):
        if self.feed is not None:
            self.feed.stop()

    # ---- REST option chain (dhanhq 2.3.0) ----

    def _client(self):
        if self._dhan is None:
            from dhanhq import DhanContext, dhanhq   # dhanhq >= 2.3 API
            self._dhan = dhanhq(DhanContext(self.client_id, self._token_provider()))
        return self._dhan

    def fetch_option_chain(self, symbol: str, expiry: str) -> Dict[str, Any]:
        """Dhan /v2/optionchain via the SDK. `expiry` is YYYY-MM-DD. Returns the SDK response
        ({} on error). The caller paces calls (Dhan: 1 per 3 s per underlying/expiry)."""
        idx = next((i for i in self.instrument_provider.fetch_instruments()
                    if i.instrument_type == "INDEX" and i.name == symbol), None)
        if idx is None:
            log.warning("No Dhan index row for %s", symbol)
            return {}
        try:
            return self._client().option_chain(under_security_id=int(idx.token),
                                               under_exchange_segment="IDX_I", expiry=expiry)
        except Exception as exc:
            log.error("Dhan option chain %s %s failed: %s", symbol, expiry, exc)
            return {}
