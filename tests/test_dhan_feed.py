"""DhanMarketFeed: connection split, paced subscribe, reconnect + resubscribe, 805 / auth
handling, stall watchdog, token scrubbing. Fake sockets only: no Dhan connection is made."""
import asyncio
import json

import pytest

from optionchain_stream.dhan import packets as P
from optionchain_stream.dhan.feed import (CapacityError, DhanMarketFeed, FeedInstrument,
                                          default_mode, plan_connections, shard_messages)


def _insts(n, seg=P.NSE_FNO, group="", start=40000, mode=""):
    return [FeedInstrument(seg, start + i, mode, group) for i in range(n)]


# ---- split ---------------------------------------------------------------------------

def test_default_modes():
    assert default_mode(P.IDX_I) == "ticker"
    assert default_mode(P.BSE_FNO) == "quote"
    assert default_mode(P.NSE_FNO) == "full"


def test_plan_connections_near_tier_sizes():
    # real 2026-10-19 near-5 counts: NIFTY 2,364 / BANKNIFTY 2,312 / SENSEX 1,846
    insts = (_insts(2364, group="NIFTY", start=1) + _insts(2312, group="BANKNIFTY", start=10001)
             + _insts(1846, P.BSE_FNO, "SENSEX", start=20001))
    shards = plan_connections(insts, per_connection=5000, max_connections=3)
    assert len(shards) == 2 and sum(map(len, shards)) == 6522
    assert all(len(s) <= 5000 for s in shards)
    groups_per_shard = [{i.group for i in s} for s in shards]
    # every group stays on exactly one socket
    assert sum(len(g) for g in groups_per_shard) == 3
    assert set().union(*groups_per_shard) == {"NIFTY", "BANKNIFTY", "SENSEX"}
    with pytest.raises(CapacityError):
        plan_connections(insts, per_connection=2000, max_connections=3)


def test_plan_connections_limits_and_dedupe():
    with pytest.raises(ValueError):
        plan_connections([], per_connection=5001)
    with pytest.raises(ValueError):
        plan_connections([], max_connections=6)
    big = _insts(12000, group="X")
    shards = plan_connections(big, per_connection=5000, max_connections=3)
    assert [len(s) for s in shards] == [5000, 5000, 2000]
    with pytest.raises(CapacityError):
        plan_connections(_insts(15001), per_connection=5000, max_connections=3)
    dup = _insts(3) + _insts(3)
    assert sum(map(len, plan_connections(dup))) == 3
    with pytest.raises(ValueError):
        plan_connections([FeedInstrument(2, 1, "full"), FeedInstrument(2, 1, "quote")])


def test_shard_messages_mode_codes_and_batches():
    shard = (_insts(150) + _insts(120, P.BSE_FNO, start=90000)
             + [FeedInstrument(P.IDX_I, 13)])
    msgs = [json.loads(m) for m in shard_messages(shard)]
    assert [m["RequestCode"] for m in msgs] == [15, 17, 17, 21, 21]
    assert max(m["InstrumentCount"] for m in msgs) <= 100
    assert sum(m["InstrumentCount"] for m in msgs) == 271


# ---- fake sockets ----------------------------------------------------------------------

class FakeWS:
    def __init__(self, frames=(), then="block"):
        self.frames = list(frames)
        self.then = then            # "block" | "raise"
        self.sent = []
        self.closed = False

    async def send(self, m):
        self.sent.append(m)

    async def recv(self):
        if self.frames:
            return self.frames.pop(0)
        if self.then == "raise":
            raise ConnectionError("socket closed by peer")
        await asyncio.Event().wait()

    async def close(self):
        self.closed = True


class Harness:
    def __init__(self, sockets, tokens=("tok-A",), stop_after=None, stop_on=None, **kw):
        self.stop_on = stop_on
        self.sockets = list(sockets)
        self.tokens = list(tokens)
        self.urls, self.made, self.packets, self.events, self.sleeps = [], [], [], [], []
        self.stop_after = stop_after if stop_after is not None else len(self.sockets)
        insts = kw.pop("instruments", None) or (_insts(150) + [FeedInstrument(P.IDX_I, 13)])
        kw.setdefault("stall_timeout_s", 0.2)
        kw.setdefault("connect_stagger_s", 0.0)
        self.feed = DhanMarketFeed("1100001", self.token, insts, on_packet=self.on_packet,
                                   on_event=self.events.append, connect=self.connect,
                                   sleep=self.sleep, **kw)

    def token(self):
        return self.tokens[0] if len(self.tokens) == 1 else self.tokens.pop(0)

    async def sleep(self, s):
        self.sleeps.append(s)
        await asyncio.sleep(0)

    def on_packet(self, pkt, shard):
        self.packets.append((type(pkt).__name__, shard))
        if self.stop_on and type(pkt).__name__ == self.stop_on:
            self.feed.stop()

    async def connect(self, url):
        self.urls.append(url)
        # every earlier socket must already be closed before a redial
        assert all(ws.closed for ws in self.made), "redial before closing the old socket"
        if len(self.made) >= self.stop_after:
            self.feed.stop()
        ws = self.sockets.pop(0) if self.sockets else FakeWS()
        self.made.append(ws)
        return ws

    def run(self, timeout=5.0):
        asyncio.run(asyncio.wait_for(self.feed.run(), timeout))

    def kinds(self):
        return [e.kind for e in self.events]


def test_resubscribe_after_disconnect_with_paced_messages():
    first = FakeWS([P.encode_oi(P.NSE_FNO, 40001, 5), P.encode_disconnect(800)])
    second = FakeWS([P.encode_ticker(P.IDX_I, 13, 25000.0, 1)])
    h = Harness([first, second], stop_after=99, stop_on="TickerPacket")
    h.run()
    assert len(h.made) == 2 and first.closed and second.closed
    assert first.sent == second.sent and len(first.sent) == 3   # 1 ticker + 2 full messages
    assert ("OIPacket", 0) in h.packets and ("TickerPacket", 0) in h.packets
    assert h.sleeps.count(0.1) >= 4          # message_interval_s between subscribe messages
    assert "server_disconnect" in h.kinds() and h.feed.stats["disconnect_codes"] == [800]
    assert h.urls[0].startswith("wss://api-feed.dhan.co?version=2&token=tok-A&clientId=1100001")


def test_805_waits_too_many_connections_interval():
    h = Harness([FakeWS([P.encode_disconnect(805)]), FakeWS()], stop_after=1,
                too_many_connections_wait_s=60.0)
    h.run()
    assert 60.0 in h.sleeps
    waits = [e.detail["seconds"] for e in h.events if e.kind == "reconnect_wait"]
    assert waits and waits[0] == 60.0


def test_auth_error_calls_back_and_redials_with_new_token():
    seen = []
    h = Harness([FakeWS([P.encode_disconnect(807)]), FakeWS()], tokens=("old", "new"),
                stop_after=1, on_auth_error=lambda shard, reason: seen.append((shard, reason)))
    h.run()
    assert seen == [(0, 807)]
    assert "token=old" in h.urls[0] and "token=new" in h.urls[1]


def test_stall_watchdog_reconnects_silent_socket():
    h = Harness([FakeWS(), FakeWS()], stop_after=1, stall_timeout_s=0.1)
    h.run()
    assert "stall" in h.kinds() and h.feed.stats["stalls"] == 1
    assert len(h.made) == 2 and h.made[0].closed


def test_errors_are_scrubbed_of_the_token():
    async def boom(url):
        h.feed.stop()
        raise OSError(f"cannot open {url}")
    h = Harness([], tokens=("SECRET-TOKEN-123",))
    h.feed._connect = boom
    h.run()
    errs = [e.detail["error"] for e in h.events if e.kind == "error"]
    assert errs and "SECRET-TOKEN-123" not in errs[0] and "***" in errs[0]


def test_two_shards_each_get_their_own_socket_and_messages():
    insts = _insts(120, group="A") + _insts(90, group="B", start=60000)
    h = Harness([FakeWS([P.encode_oi(P.NSE_FNO, 40000, 1)]),
                 FakeWS([P.encode_oi(P.NSE_FNO, 60000, 2)])], stop_after=2,
                instruments=insts, per_connection=150, max_connections=3)
    h.run()
    assert len(h.feed.shards) == 2
    sent = [sum(json.loads(m)["InstrumentCount"] for m in ws.sent) for ws in h.made[:2]]
    assert sorted(sent) == [90, 120]
    assert {s for _, s in h.packets} == {0, 1}


def test_no_token_backs_off_without_connecting():
    h = Harness([], tokens=(None,))
    calls = {"n": 0}

    def tok():
        calls["n"] += 1
        if calls["n"] >= 2:
            h.feed.stop()
        return None
    h.feed._token_provider = tok
    h.run()
    assert h.urls == [] and h.kinds().count("no_token") >= 1
