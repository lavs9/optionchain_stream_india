"""Dhan Live Market Feed v2 client: connection split, paced subscribe, reconnect + resubscribe,
stall watchdog. asyncio, no login: the caller supplies the access token.

Dhan limits (docs.dhanhq.co/api/v2/live-market-feed):
  * up to 5 WebSocket connections per user, 5,000 instruments per connection;
  * up to 100 instruments per subscribe JSON message;
  * the server pings every 10 s and closes a client silent for more than 40 s (the
    `websockets` library answers pings automatically);
  * a 6th connection makes Dhan drop the OLDEST one with disconnect code 805.

So this client:
  * splits the instruments over at most `max_connections` sockets (default 3, hard cap 5),
    `per_connection` instruments each (hard cap 5,000), keeping each `group` (e.g. one
    underlying+expiry) on one socket where it fits;
  * sends subscribe messages of <= 100 instruments, `message_interval_s` apart;
  * on any error / server disconnect / stall: closes the socket explicitly BEFORE redialling
    (so a reconnect never stacks toward Dhan's 5-socket cap), backs off, reconnects with the
    token `token_provider()` returns now, and re-subscribes that connection's full list;
  * 805 from the server waits `too_many_connections_wait_s` (another client holds a slot);
  * 807-810 (token) calls `on_auth_error(shard, reason)` so the caller can renew the token
    (this module never logs in), then redials with whatever `token_provider()` returns;
  * stall watchdog: a connected socket that delivers no frame for `stall_timeout_s` is closed
    and redialled.

The token is part of the URL; it is scrubbed from every error text this module emits.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, Optional, Sequence

from optionchain_stream.dhan import packets as P

log = logging.getLogger(__name__)

FEED_URL = "wss://api-feed.dhan.co"
DHAN_MAX_CONNECTIONS = 5
DHAN_MAX_PER_CONNECTION = 5000


@dataclass(frozen=True)
class FeedInstrument:
    segment: int                 # packets.NSE_FNO / BSE_FNO / IDX_I ...
    security_id: int
    mode: str = ""               # "ticker" | "quote" | "full"; "" = default_mode(segment)
    group: str = ""              # packing key: instruments of one group share a socket

    @property
    def key(self) -> tuple[int, int]:
        return (self.segment, self.security_id)

    @property
    def resolved_mode(self) -> str:
        return self.mode or default_mode(self.segment)


def default_mode(segment: int) -> str:
    """Index -> ticker. BSE_FNO -> quote (Dhan answers a Full subscribe on BSE_FNO with no
    packets; Quote mode also streams OI packets). Everything else -> full (LTP, volume, OI and
    5-level depth in one packet)."""
    if segment == P.IDX_I:
        return "ticker"
    if segment == P.BSE_FNO:
        return "quote"
    return "full"


class CapacityError(ValueError):
    pass


def plan_connections(instruments: Iterable[FeedInstrument], *,
                     per_connection: int = DHAN_MAX_PER_CONNECTION,
                     max_connections: int = 3) -> list[list[FeedInstrument]]:
    """Split instruments over sockets. Duplicates (same segment+id) are dropped (first wins);
    the same instrument asked in two modes is an error. Groups are packed first-fit-decreasing
    (largest first) so a group stays on one socket when it fits; a group bigger than
    `per_connection` is cut into chunks. Raises CapacityError if more than `max_connections`
    sockets would be needed. Deterministic for a given input."""
    if not 1 <= per_connection <= DHAN_MAX_PER_CONNECTION:
        raise ValueError(f"per_connection must be 1..{DHAN_MAX_PER_CONNECTION}")
    if not 1 <= max_connections <= DHAN_MAX_CONNECTIONS:
        raise ValueError(f"max_connections must be 1..{DHAN_MAX_CONNECTIONS}")
    seen: dict[tuple[int, int], FeedInstrument] = {}
    groups: dict[str, list[FeedInstrument]] = {}
    for inst in instruments:
        prev = seen.get(inst.key)
        if prev is not None:
            if prev.resolved_mode != inst.resolved_mode:
                raise ValueError(f"instrument {inst.key} requested as {prev.resolved_mode} "
                                 f"and {inst.resolved_mode}")
            continue
        seen[inst.key] = inst
        groups.setdefault(inst.group, []).append(inst)
    pieces: list[list[FeedInstrument]] = []
    for name in sorted(groups):
        items = groups[name]
        for i in range(0, len(items), per_connection):
            pieces.append(items[i:i + per_connection])
    pieces.sort(key=len, reverse=True)
    shards: list[list[FeedInstrument]] = []
    for piece in pieces:
        for shard in shards:
            if len(shard) + len(piece) <= per_connection:
                shard.extend(piece)
                break
        else:
            shards.append(list(piece))
    if len(shards) > max_connections:
        raise CapacityError(f"{len(seen)} instruments need {len(shards)} connections of "
                            f"<= {per_connection}; max_connections={max_connections}")
    return shards


def shard_messages(shard: Sequence[FeedInstrument],
                   per_message: int = P.MAX_INSTRUMENTS_PER_MESSAGE) -> list[str]:
    """All subscribe messages for one socket, grouped by mode (ticker, quote, full)."""
    out: list[str] = []
    for mode in ("ticker", "quote", "full"):
        keys = sorted(i.key for i in shard if i.resolved_mode == mode)
        if keys:
            out.extend(P.subscribe_messages(keys, P.MODE_REQUEST_CODES[mode], per_message))
    return out


def feed_url(client_id: str, token: str) -> str:
    return f"{FEED_URL}?version=2&token={token}&clientId={client_id}&authType=2"


def scrub(text: Any, secrets: Iterable[Optional[str]]) -> str:
    s = str(text)
    for sec in secrets:
        if sec:
            s = s.replace(sec, "***")
    return s


@dataclass(frozen=True)
class FeedEvent:
    kind: str     # connected | subscribed | server_disconnect | stall | error | auth_error |
                  # no_token | reconnect_wait | closed | decode_error
    shard: int
    detail: dict = field(default_factory=dict)


class ServerDisconnect(RuntimeError):
    def __init__(self, reason: int):
        super().__init__(f"Dhan feed disconnect {reason}: "
                         f"{P.DISCONNECT_REASONS.get(reason, 'unknown')}")
        self.reason = reason


class _Stall(RuntimeError):
    pass


async def _default_connect(url: str):
    import websockets  # dependency of dhanhq; listed in the [dhan] extra
    return await websockets.connect(url, max_size=None, open_timeout=20, close_timeout=5)


class DhanMarketFeed:
    """Run with ``await feed.run()``; stop with ``feed.stop()``.

    on_packet(packet, shard_index) is called for every decoded packet except disconnect
    packets (which drive reconnects and are reported as FeedEvent("server_disconnect")).
    It runs on the event loop: keep it fast (e.g. ChainAssembler.on_packet)."""

    def __init__(self, client_id: str, token_provider: Callable[[], Optional[str]],
                 instruments: Iterable[FeedInstrument], *,
                 on_packet: Callable[[P.AnyPacket, int], None],
                 on_event: Optional[Callable[[FeedEvent], None]] = None,
                 on_auth_error: Optional[Callable[[int, int], Any]] = None,
                 per_connection: int = DHAN_MAX_PER_CONNECTION, max_connections: int = 3,
                 message_interval_s: float = 0.1, stall_timeout_s: float = 30.0,
                 backoff_initial_s: float = 2.0, backoff_max_s: float = 30.0,
                 too_many_connections_wait_s: float = 60.0, connect_stagger_s: float = 5.0,
                 healthy_session_s: float = 60.0,
                 connect: Optional[Callable[[str], Awaitable[Any]]] = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 clock: Callable[[], float] = time.monotonic):
        self.client_id = client_id
        self._token_provider = token_provider
        self.shards = plan_connections(instruments, per_connection=per_connection,
                                       max_connections=max_connections)
        self._on_packet = on_packet
        self._on_event = on_event
        self._on_auth_error = on_auth_error
        self.message_interval_s = message_interval_s
        self.stall_timeout_s = stall_timeout_s
        self.backoff_initial_s = backoff_initial_s
        self.backoff_max_s = backoff_max_s
        self.too_many_connections_wait_s = too_many_connections_wait_s
        self.connect_stagger_s = connect_stagger_s
        self.healthy_session_s = healthy_session_s
        self._connect = connect or _default_connect
        self._sleep = sleep
        self._clock = clock
        self._stop = asyncio.Event()
        self._sockets: dict[int, Any] = {}
        self.stats = {"connects": 0, "subscribe_msgs": 0, "frames": 0, "packets": 0,
                      "decode_errors": 0, "stalls": 0, "disconnect_codes": [], "errors": 0}

    # ---- public ----

    @property
    def instrument_count(self) -> int:
        return sum(len(s) for s in self.shards)

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        tasks = [asyncio.create_task(self._run_shard(i)) for i in range(len(self.shards))]
        try:
            await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                t.cancel()
            for i in list(self._sockets):
                await self._close(i)

    # ---- internals ----

    def _emit(self, kind: str, shard: int, **detail) -> None:
        if self._on_event is not None:
            try:
                self._on_event(FeedEvent(kind, shard, detail))
            except Exception:  # an observer must never break the feed
                log.exception("on_event callback failed")

    async def _close(self, shard: int) -> None:
        ws = self._sockets.pop(shard, None)
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
            self._emit("closed", shard)

    async def _wait(self, seconds: float) -> None:
        if seconds <= 0 or self._stop.is_set():
            return
        stopper = asyncio.ensure_future(self._stop.wait())
        sleeper = asyncio.ensure_future(self._sleep(seconds))
        try:
            await asyncio.wait({stopper, sleeper}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            stopper.cancel()
            sleeper.cancel()

    async def _subscribe(self, shard: int, ws) -> int:
        msgs = shard_messages(self.shards[shard])
        for n, m in enumerate(msgs):
            if n:
                await self._sleep(self.message_interval_s)
            await ws.send(m)
            self.stats["subscribe_msgs"] += 1
        return len(msgs)

    async def _session(self, shard: int, token: str) -> None:
        ws = await self._connect(feed_url(self.client_id, token))
        self._sockets[shard] = ws
        self.stats["connects"] += 1
        self._emit("connected", shard, instruments=len(self.shards[shard]))
        n = await self._subscribe(shard, ws)
        self._emit("subscribed", shard, messages=n, instruments=len(self.shards[shard]))
        last = self._clock()
        poll = max(0.01, min(1.0, self.stall_timeout_s / 4))
        while not self._stop.is_set():
            try:
                frame = await asyncio.wait_for(ws.recv(), timeout=poll)
            except asyncio.TimeoutError:
                if self._clock() - last > self.stall_timeout_s:
                    raise _Stall(f"no frame for {self.stall_timeout_s:.0f}s")
                continue
            last = self._clock()
            self.stats["frames"] += 1
            if not isinstance(frame, (bytes, bytearray)):
                continue
            try:
                for pkt in P.iter_packets(bytes(frame)):
                    if isinstance(pkt, P.DisconnectPacket):
                        raise ServerDisconnect(pkt.reason)
                    self.stats["packets"] += 1
                    self._on_packet(pkt, shard)
            except P.PacketError as exc:
                self.stats["decode_errors"] += 1
                self._emit("decode_error", shard, error=str(exc))

    async def _run_shard(self, shard: int) -> None:
        await self._wait(shard * self.connect_stagger_s)
        backoff = self.backoff_initial_s
        while not self._stop.is_set():
            token = None
            started = self._clock()
            floor = 0.0           # minimum wait imposed by the disconnect reason
            try:
                token = self._token_provider()
                if not token:
                    self._emit("no_token", shard)
                else:
                    await self._session(shard, token)
            except ServerDisconnect as exc:
                self.stats["disconnect_codes"].append(exc.reason)
                self._emit("server_disconnect", shard, reason=exc.reason, text=str(exc))
                if exc.reason == 805:
                    floor = self.too_many_connections_wait_s
                elif exc.reason in P.AUTH_REASONS:
                    self._emit("auth_error", shard, reason=exc.reason)
                    if self._on_auth_error is not None:
                        try:
                            res = self._on_auth_error(shard, exc.reason)
                            if asyncio.iscoroutine(res):
                                await res
                        except Exception as cb_exc:
                            self._emit("error", shard, error=scrub(cb_exc, [token]))
            except _Stall as exc:
                self.stats["stalls"] += 1
                self._emit("stall", shard, error=str(exc))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.stats["errors"] += 1
                self._emit("error", shard, error=scrub(exc, [token]))
            finally:
                await self._close(shard)  # explicit close before any redial
            if self._stop.is_set():
                break
            if self._clock() - started >= self.healthy_session_s:
                backoff = self.backoff_initial_s   # a long healthy session resets the backoff
            wait = max(backoff, floor)
            self._emit("reconnect_wait", shard, seconds=wait)
            await self._wait(wait)
            backoff = min(self.backoff_max_s, backoff * 2)
