"""Tick -> live option chain state, plus a 1-minute snapshot emitter (broker-agnostic core,
fed today by the Dhan WS packets in optionchain_stream.dhan).

Vendor-raw only: every field is the last value the feed sent, unchanged; a field that was
never received is None (never 0). Nothing here computes IV, greeks or any other derived
value (see optionchain_stream.iv for IV, which is a separate output).

Usage (as a library):

    asm = ChainAssembler(contracts)                  # ContractMeta per instrument
    feed = DhanMarketFeed(..., on_packet=asm.on_packet)
    snap = MinuteSnapshotter(asm, on_snapshot=write_rows)   # or: async for s in snap: ...
    await asyncio.gather(feed.run(), snap.run())
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import time
from dataclasses import dataclass, fields
from typing import Awaitable, Callable, Iterable, Optional, Union
from zoneinfo import ZoneInfo

from optionchain_stream.dhan import packets as P

IST = ZoneInfo("Asia/Kolkata")
UTC = _dt.timezone.utc
SESSION_IST = (_dt.time(9, 15), _dt.time(15, 30))


@dataclass(frozen=True)
class ContractMeta:
    """One streamed instrument. option_type: "CE" | "PE" | "FUT" | "INDEX"."""
    segment: int
    security_id: int
    underlying: str
    option_type: str
    expiry: Optional[_dt.date] = None
    strike: float = 0.0
    symbol: str = ""
    lot_size: int = 0

    @property
    def key(self) -> tuple[int, int]:
        return (self.segment, self.security_id)


@dataclass(frozen=True)
class LegSnapshot:
    """Vendor-raw state of one instrument at snapshot time. None = never received."""
    meta: ContractMeta
    ltp: Optional[float] = None
    ltq: Optional[int] = None
    ltt: Optional[int] = None              # raw LTT as sent (see packets.ltt_to_utc)
    atp: Optional[float] = None
    volume: Optional[int] = None           # cumulative day volume
    total_buy_qty: Optional[int] = None
    total_sell_qty: Optional[int] = None
    oi: Optional[int] = None
    oi_day_high: Optional[int] = None
    oi_day_low: Optional[int] = None
    day_open: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    day_close: Optional[float] = None
    prev_close: Optional[float] = None
    prev_oi: Optional[int] = None          # prev-close packet bytes 12-15 (encoding unverified)
    depth: Optional[tuple] = None          # 5 x packets.DepthLevel (Full mode only)
    last_packet_at: Optional[float] = None  # wall clock (epoch s) of the last packet applied
    packets: int = 0

    @property
    def bid(self) -> Optional[float]:
        return self.depth[0].bid_price if self.depth else None

    @property
    def ask(self) -> Optional[float]:
        return self.depth[0].ask_price if self.depth else None

    @property
    def bid_qty(self) -> Optional[int]:
        return self.depth[0].bid_qty if self.depth else None

    @property
    def ask_qty(self) -> Optional[int]:
        return self.depth[0].ask_qty if self.depth else None

    @property
    def last_trade_utc(self) -> Optional[_dt.datetime]:
        return P.ltt_to_utc(self.ltt) if self.ltt else None


_LEG_FIELDS = [f.name for f in fields(LegSnapshot) if f.name != "meta"]


class _Leg:
    __slots__ = ("meta", *_LEG_FIELDS)

    def __init__(self, meta: ContractMeta):
        self.meta = meta
        for name in _LEG_FIELDS:
            setattr(self, name, None)
        self.packets = 0

    def freeze(self) -> LegSnapshot:
        return LegSnapshot(self.meta, **{n: getattr(self, n) for n in _LEG_FIELDS})


@dataclass(frozen=True)
class StrikeSnapshot:
    strike: float
    ce: Optional[LegSnapshot]
    pe: Optional[LegSnapshot]


@dataclass(frozen=True)
class ExpirySnapshot:
    underlying: str
    expiry: _dt.date
    spot: Optional[float]                  # index LTP (vendor-raw)
    future: Optional[LegSnapshot]          # the future of this expiry if streamed, else None
    strikes: tuple                         # StrikeSnapshot, ascending strike
    call_oi_total: Optional[int]           # sum of CE OI over strikes with OI; None if none
    put_oi_total: Optional[int]


@dataclass(frozen=True)
class ChainSnapshot:
    at: _dt.datetime                       # aware UTC: the minute close the snapshot is for
    expiries: tuple                        # ExpirySnapshot, by (underlying, expiry)
    index: dict                            # underlying -> LegSnapshot of the index

    def get(self, underlying: str, expiry: _dt.date) -> Optional[ExpirySnapshot]:
        for e in self.expiries:
            if e.underlying == underlying and e.expiry == expiry:
                return e
        return None


class ChainAssembler:
    """Holds the latest vendor-raw state per contract and builds chain snapshots."""

    def __init__(self, contracts: Iterable[ContractMeta], *, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._legs: dict[tuple[int, int], _Leg] = {}
        for c in contracts:
            self._legs[c.key] = _Leg(c)
        self.unknown_packets = 0

    @property
    def contracts(self) -> list[ContractMeta]:
        return [leg.meta for leg in self._legs.values()]

    def leg(self, segment: int, security_id: int) -> Optional[LegSnapshot]:
        leg = self._legs.get((segment, security_id))
        return leg.freeze() if leg else None

    def on_packet(self, pkt: P.AnyPacket, shard: Optional[int] = None) -> None:
        """Apply one decoded packet (signature matches DhanMarketFeed's on_packet)."""
        leg = self._legs.get(pkt.key)
        if leg is None:
            self.unknown_packets += 1
            return
        if isinstance(pkt, P.TickerPacket):
            leg.ltp, leg.ltt = pkt.ltp, pkt.ltt
        elif isinstance(pkt, P.FullPacket):
            for n in ("ltp", "ltq", "ltt", "atp", "volume", "total_buy_qty", "total_sell_qty",
                      "oi", "oi_day_high", "oi_day_low", "day_open", "day_high", "day_low",
                      "day_close", "depth"):
                setattr(leg, n, getattr(pkt, n))
        elif isinstance(pkt, P.QuotePacket):
            for n in ("ltp", "ltq", "ltt", "atp", "volume", "total_buy_qty", "total_sell_qty",
                      "day_open", "day_high", "day_low", "day_close"):
                setattr(leg, n, getattr(pkt, n))
        elif isinstance(pkt, P.OIPacket):
            leg.oi = pkt.oi
        elif isinstance(pkt, P.PrevClosePacket):
            leg.prev_close, leg.prev_oi = pkt.prev_close, pkt.prev_oi
        else:
            return
        leg.packets += 1
        leg.last_packet_at = self._clock()

    def snapshot(self, at: Optional[_dt.datetime] = None) -> ChainSnapshot:
        """Freeze the current state. `at` (aware) defaults to now; stored as UTC."""
        at = (at or _dt.datetime.now(UTC)).astimezone(UTC)
        index: dict[str, LegSnapshot] = {}
        futures: dict[tuple[str, _dt.date], LegSnapshot] = {}
        chains: dict[tuple[str, _dt.date], dict[float, dict[str, LegSnapshot]]] = {}
        for leg in self._legs.values():
            m = leg.meta
            if m.option_type == "INDEX":
                index[m.underlying] = leg.freeze()
            elif m.option_type == "FUT" and m.expiry is not None:
                futures[(m.underlying, m.expiry)] = leg.freeze()
            elif m.option_type in ("CE", "PE") and m.expiry is not None:
                chains.setdefault((m.underlying, m.expiry), {}).setdefault(
                    m.strike, {})[m.option_type] = leg.freeze()
        out = []
        for (und, exp) in sorted(chains):
            by_strike = chains[(und, exp)]
            strikes = tuple(StrikeSnapshot(k, s.get("CE"), s.get("PE"))
                            for k, s in sorted(by_strike.items()))
            ce_oi = [s.ce.oi for s in strikes if s.ce is not None and s.ce.oi is not None]
            pe_oi = [s.pe.oi for s in strikes if s.pe is not None and s.pe.oi is not None]
            idx = index.get(und)
            out.append(ExpirySnapshot(
                underlying=und, expiry=exp, spot=idx.ltp if idx else None,
                future=futures.get((und, exp)), strikes=strikes,
                call_oi_total=sum(ce_oi) if ce_oi else None,
                put_oi_total=sum(pe_oi) if pe_oi else None))
        return ChainSnapshot(at=at, expiries=tuple(out), index=index)


SnapshotCallback = Callable[[ChainSnapshot], Union[None, Awaitable[None]]]


def _in_session(close_utc: _dt.datetime, session: Optional[tuple[_dt.time, _dt.time]]) -> bool:
    """A minute close belongs to the session if it is in (open, close] IST: 09:16 .. 15:30."""
    if session is None:
        return True
    t = close_utc.astimezone(IST).time()
    return session[0] < t <= session[1]


class MinuteSnapshotter:
    """Emits ChainAssembler.snapshot() at every minute close (hh:mm:00, `interval_s` = 60 by
    default), only inside `session` (IST; default 09:15-15:30, i.e. closes 09:16..15:30; None =
    always). Use the callback, or iterate: ``async for snap in snapshotter: ...``."""

    def __init__(self, assembler: ChainAssembler, on_snapshot: Optional[SnapshotCallback] = None,
                 *, interval_s: int = 60,
                 session: Optional[tuple[_dt.time, _dt.time]] = SESSION_IST,
                 clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        if interval_s <= 0 or 3600 % interval_s:
            raise ValueError("interval_s must divide 3600")
        self.assembler = assembler
        self._on_snapshot = on_snapshot
        self.interval_s = interval_s
        self.session = session
        self._clock = clock
        self._sleep = sleep
        self._stop = asyncio.Event()
        self._queue: Optional[asyncio.Queue] = None
        self.emitted = 0

    def stop(self) -> None:
        self._stop.set()

    def next_boundary(self, now: float) -> float:
        return (int(now) // self.interval_s + 1) * self.interval_s

    async def run(self, *, max_snapshots: Optional[int] = None) -> None:
        while not self._stop.is_set():
            boundary = self.next_boundary(self._clock())
            delay = boundary - self._clock()
            if delay > 0:
                await self._sleep(delay)
            if self._stop.is_set():
                break
            at = _dt.datetime.fromtimestamp(boundary, UTC)
            if not _in_session(at, self.session):
                continue
            snap = self.assembler.snapshot(at)
            self.emitted += 1
            if self._on_snapshot is not None:
                res = self._on_snapshot(snap)
                if asyncio.iscoroutine(res):
                    await res
            if self._queue is not None:
                self._queue.put_nowait(snap)
            if max_snapshots is not None and self.emitted >= max_snapshots:
                break
        if self._queue is not None:
            self._queue.put_nowait(None)

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        if self._queue is None:
            self._queue = asyncio.Queue()
        while True:
            snap = await self._queue.get()
            if snap is None:
                return
            yield snap
