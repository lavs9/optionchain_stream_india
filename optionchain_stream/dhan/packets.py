"""Dhan Live Market Feed (v2) binary packets: constants, request messages, decoders.

Layout source: https://docs.dhanhq.co/api/v2/live-market-feed (+ Annexure). Every packet is
little-endian and starts with an 8-byte header::

    byte 0      feed response code
    bytes 1-2   int16 message length
    byte 3      exchange segment (Annexure enum)
    bytes 4-7   int32 security id

The struct formats below are the same ones the official ``dhanhq`` 2.3.0 SDK uses
(``MarketFeed.process_*``); ``tests/test_dhan_packets.py`` cross-checks them against the SDK.

Values are returned exactly as received (vendor-raw). The only helper that interprets a value
is :func:`ltt_to_utc`, which is opt-in (see its docstring).
"""
from __future__ import annotations

import datetime as _dt
import json
import struct
from dataclasses import dataclass, field
from typing import Iterator, Optional, Sequence, Union

# ---- Annexure: exchange segments -------------------------------------------------------
IDX_I, NSE_EQ, NSE_FNO, BSE_EQ, MCX_COMM, BSE_FNO = 0, 1, 2, 4, 5, 8
SEGMENT_NAMES = {IDX_I: "IDX_I", NSE_EQ: "NSE_EQ", NSE_FNO: "NSE_FNO", BSE_EQ: "BSE_EQ",
                 MCX_COMM: "MCX_COMM", BSE_FNO: "BSE_FNO"}
SEGMENT_CODES = {v: k for k, v in SEGMENT_NAMES.items()}

# ---- Annexure: feed request codes (unsubscribe = subscribe + 1) ------------------------
REQ_DISCONNECT = 12
REQ_TICKER, REQ_QUOTE, REQ_FULL = 15, 17, 21
MODE_REQUEST_CODES = {"ticker": REQ_TICKER, "quote": REQ_QUOTE, "full": REQ_FULL}
MAX_INSTRUMENTS_PER_MESSAGE = 100   # "only send upto 100 instruments in a single JSON message"

# ---- Annexure: feed response codes -----------------------------------------------------
RESP_INDEX, RESP_TICKER, RESP_QUOTE, RESP_OI, RESP_PREV_CLOSE = 1, 2, 4, 5, 6
RESP_MARKET_STATUS, RESP_FULL, RESP_DISCONNECT = 7, 8, 50

# ---- Annexure: Data API / disconnect reason codes --------------------------------------
DISCONNECT_REASONS = {
    800: "internal server error",
    804: "requested number of instruments exceeds limit",
    805: "too many requests or connections (more than 5 sockets: the oldest is dropped)",
    806: "Data APIs not subscribed",
    807: "access token expired",
    808: "authentication failed",
    809: "access token invalid",
    810: "client id invalid",
}
AUTH_REASONS = {807, 808, 809, 810}

HEADER = struct.Struct("<BHBI")                       # 8
_TICKER = struct.Struct("<BHBIfI")                    # 16: ltp, ltt
_PREV_CLOSE = struct.Struct("<BHBIfI")                # 16: prev close, prev-day OI (docs: int32)
_QUOTE = struct.Struct("<BHBIfHIfIIIffff")            # 50
_OI = struct.Struct("<BHBII")                         # 12
_FULL = struct.Struct("<BHBIfHIfIIIIIIffff")          # 62, then 5 x 20-byte depth levels
_DEPTH = struct.Struct("<IIHHff")                     # 20
_DISCONNECT = struct.Struct("<BHBIH")                 # 10
FULL_SIZE = _FULL.size + 5 * _DEPTH.size              # 162

PACKET_SIZES = {RESP_INDEX: _TICKER.size, RESP_TICKER: _TICKER.size, RESP_QUOTE: _QUOTE.size,
                RESP_OI: _OI.size, RESP_PREV_CLOSE: _PREV_CLOSE.size,
                RESP_MARKET_STATUS: HEADER.size, RESP_FULL: FULL_SIZE,
                RESP_DISCONNECT: _DISCONNECT.size}

IST_OFFSET_S = 19800


@dataclass(frozen=True)
class DepthLevel:
    bid_qty: int
    ask_qty: int
    bid_orders: int
    ask_orders: int
    bid_price: float
    ask_price: float


@dataclass(frozen=True)
class Packet:
    code: int
    segment: int
    security_id: int

    @property
    def key(self) -> tuple[int, int]:
        return (self.segment, self.security_id)


@dataclass(frozen=True)
class TickerPacket(Packet):            # code 2 (and code 1, index, same layout)
    ltp: float
    ltt: int                           # raw LTT as sent (see ltt_to_utc)


@dataclass(frozen=True)
class PrevClosePacket(Packet):         # code 6
    prev_close: float
    prev_oi: int                       # bytes 12-15 read as int32 per the docs (UNVERIFIED)
    prev_oi_raw: bytes = b""           # the 4 raw bytes, for callers that decode differently


@dataclass(frozen=True)
class QuotePacket(Packet):             # code 4
    ltp: float
    ltq: int
    ltt: int
    atp: float
    volume: int
    total_sell_qty: int
    total_buy_qty: int
    day_open: float
    day_close: float                   # "only sent post market close"
    day_high: float
    day_low: float


@dataclass(frozen=True)
class OIPacket(Packet):                # code 5
    oi: int


@dataclass(frozen=True)
class FullPacket(Packet):              # code 8
    ltp: float
    ltq: int
    ltt: int
    atp: float
    volume: int
    total_sell_qty: int
    total_buy_qty: int
    oi: int
    oi_day_high: int                   # NSE_FNO only
    oi_day_low: int                    # NSE_FNO only
    day_open: float
    day_close: float
    day_high: float
    day_low: float
    depth: tuple[DepthLevel, ...] = field(default_factory=tuple)   # 5 levels


@dataclass(frozen=True)
class MarketStatusPacket(Packet):      # code 7
    pass


@dataclass(frozen=True)
class DisconnectPacket(Packet):        # code 50
    reason: int

    @property
    def reason_text(self) -> str:
        return DISCONNECT_REASONS.get(self.reason, "unknown")


@dataclass(frozen=True)
class UnknownPacket(Packet):
    raw: bytes = b""


AnyPacket = Union[TickerPacket, PrevClosePacket, QuotePacket, OIPacket, FullPacket,
                  MarketStatusPacket, DisconnectPacket, UnknownPacket]


class PacketError(ValueError):
    """A frame too short for the packet type its first byte announces."""


def decode_packet(data: bytes) -> AnyPacket:
    """Decode ONE packet starting at data[0]. Raises PacketError if it is truncated."""
    if len(data) < HEADER.size:
        raise PacketError(f"packet shorter than the 8-byte header ({len(data)} bytes)")
    code, _length, seg, sid = HEADER.unpack_from(data, 0)
    need = PACKET_SIZES.get(code)
    if need is not None and len(data) < need:
        raise PacketError(f"code {code} needs {need} bytes, got {len(data)}")
    if code in (RESP_TICKER, RESP_INDEX):
        _, _, _, _, ltp, ltt = _TICKER.unpack_from(data, 0)
        return TickerPacket(code, seg, sid, ltp, ltt)
    if code == RESP_PREV_CLOSE:
        _, _, _, _, pc, poi = _PREV_CLOSE.unpack_from(data, 0)
        return PrevClosePacket(code, seg, sid, pc, poi, bytes(data[12:16]))
    if code == RESP_QUOTE:
        v = _QUOTE.unpack_from(data, 0)
        return QuotePacket(code, seg, sid, *v[4:])
    if code == RESP_OI:
        return OIPacket(code, seg, sid, _OI.unpack_from(data, 0)[4])
    if code == RESP_FULL:
        v = _FULL.unpack_from(data, 0)
        depth = tuple(DepthLevel(*_DEPTH.unpack_from(data, _FULL.size + i * _DEPTH.size))
                      for i in range(5))
        return FullPacket(code, seg, sid, *v[4:], depth=depth)
    if code == RESP_MARKET_STATUS:
        return MarketStatusPacket(code, seg, sid)
    if code == RESP_DISCONNECT:
        return DisconnectPacket(code, seg, sid, _DISCONNECT.unpack_from(data, 0)[4])
    return UnknownPacket(code, seg, sid, bytes(data))


def iter_packets(frame: bytes) -> Iterator[AnyPacket]:
    """Decode every packet in one WebSocket frame. Dhan normally sends one packet per frame;
    if several known fixed-size packets are concatenated they are split by size. An unknown
    code ends the walk (the rest of the frame is returned as one UnknownPacket)."""
    off = 0
    while off < len(frame):
        chunk = frame[off:]
        pkt = decode_packet(chunk)
        size = PACKET_SIZES.get(pkt.code)
        yield pkt
        if size is None:
            return
        off += size


def ltt_to_utc(raw_ltt: int) -> Optional[_dt.datetime]:
    """Dhan's LTT, as observed on prod (Findia, 2026-10-17), is IST wall-clock time encoded as
    epoch seconds: read as UTC, Friday's last trades show 15:39 *UTC*. This undoes the +05:30
    shift and returns an aware UTC datetime. 0 -> None. The raw value stays on the packet."""
    if not raw_ltt:
        return None
    return _dt.datetime.fromtimestamp(raw_ltt - IST_OFFSET_S, _dt.timezone.utc)


def subscribe_messages(instruments: Sequence[tuple[int, int]], request_code: int,
                       per_message: int = MAX_INSTRUMENTS_PER_MESSAGE) -> list[str]:
    """JSON subscribe (or unsubscribe = code + 1) messages, at most `per_message` instruments
    each. `instruments` = (segment code, security id) pairs."""
    if not 1 <= per_message <= MAX_INSTRUMENTS_PER_MESSAGE:
        raise ValueError(f"per_message must be 1..{MAX_INSTRUMENTS_PER_MESSAGE}")
    items = list(instruments)
    out = []
    for i in range(0, len(items), per_message):
        batch = items[i:i + per_message]
        out.append(json.dumps({
            "RequestCode": request_code,
            "InstrumentCount": len(batch),
            "InstrumentList": [{"ExchangeSegment": SEGMENT_NAMES.get(seg, str(seg)),
                                "SecurityId": str(sid)} for seg, sid in batch],
        }))
    return out


# ---- fixture helpers (tests / replay): build packets from the documented layout ---------

def encode_ticker(seg: int, sid: int, ltp: float, ltt: int, code: int = RESP_TICKER) -> bytes:
    return _TICKER.pack(code, _TICKER.size, seg, sid, ltp, ltt)


def encode_prev_close(seg: int, sid: int, prev_close: float, prev_oi: int) -> bytes:
    return _PREV_CLOSE.pack(RESP_PREV_CLOSE, _PREV_CLOSE.size, seg, sid, prev_close, prev_oi)


def encode_quote(seg: int, sid: int, *, ltp: float, ltq: int, ltt: int, atp: float,
                 volume: int, total_sell_qty: int = 0, total_buy_qty: int = 0,
                 day_open: float = 0.0, day_close: float = 0.0, day_high: float = 0.0,
                 day_low: float = 0.0) -> bytes:
    return _QUOTE.pack(RESP_QUOTE, _QUOTE.size, seg, sid, ltp, ltq, ltt, atp, volume,
                       total_sell_qty, total_buy_qty, day_open, day_close, day_high, day_low)


def encode_oi(seg: int, sid: int, oi: int) -> bytes:
    return _OI.pack(RESP_OI, _OI.size, seg, sid, oi)


def encode_full(seg: int, sid: int, *, ltp: float, ltq: int, ltt: int, atp: float, volume: int,
                total_sell_qty: int = 0, total_buy_qty: int = 0, oi: int = 0,
                oi_day_high: int = 0, oi_day_low: int = 0, day_open: float = 0.0,
                day_close: float = 0.0, day_high: float = 0.0, day_low: float = 0.0,
                depth: Sequence[DepthLevel] = ()) -> bytes:
    levels = list(depth) + [DepthLevel(0, 0, 0, 0, 0.0, 0.0)] * (5 - len(depth))
    head = _FULL.pack(RESP_FULL, FULL_SIZE, seg, sid, ltp, ltq, ltt, atp, volume,
                      total_sell_qty, total_buy_qty, oi, oi_day_high, oi_day_low,
                      day_open, day_close, day_high, day_low)
    return head + b"".join(_DEPTH.pack(lv.bid_qty, lv.ask_qty, lv.bid_orders, lv.ask_orders,
                                       lv.bid_price, lv.ask_price) for lv in levels[:5])


def encode_disconnect(reason: int) -> bytes:
    return _DISCONNECT.pack(RESP_DISCONNECT, _DISCONNECT.size, 0, 0, reason)
