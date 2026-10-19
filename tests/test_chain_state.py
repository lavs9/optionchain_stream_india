"""ChainAssembler (vendor-raw state, None when never received) and MinuteSnapshotter."""
import asyncio
import datetime as dt
import os

import pytest

from optionchain_stream.chain_state import ChainAssembler, ContractMeta, MinuteSnapshotter
from optionchain_stream.dhan import packets as P
from optionchain_stream.dhan.universe import near_expiry_universe
from optionchain_stream.instrument_master.dhan_provider import parse_scrip_master

UTC = dt.timezone.utc
EXP = dt.date(2026, 10, 27)
NIFTY = [
    ContractMeta(P.IDX_I, 13, "NIFTY", "INDEX"),
    ContractMeta(P.NSE_FNO, 900, "NIFTY", "FUT", EXP, 0.0, "NIFTY FUT", 75),
    ContractMeta(P.NSE_FNO, 1, "NIFTY", "CE", EXP, 25000.0, "NIFTY 25000 CE", 75),
    ContractMeta(P.NSE_FNO, 2, "NIFTY", "PE", EXP, 25000.0, "NIFTY 25000 PE", 75),
    ContractMeta(P.NSE_FNO, 3, "NIFTY", "CE", EXP, 25100.0, "NIFTY 25100 CE", 75),
    ContractMeta(P.NSE_FNO, 4, "NIFTY", "PE", EXP, 25100.0, "NIFTY 25100 PE", 75),
]
LVL = P.DepthLevel(750, 600, 5, 4, 120.0, 120.5)


def _fed():
    clock = [1000.0]
    a = ChainAssembler(NIFTY, clock=lambda: clock[0])
    a.on_packet(P.decode_packet(P.encode_ticker(P.IDX_I, 13, 25050.0, 1)))
    a.on_packet(P.decode_packet(P.encode_full(P.NSE_FNO, 1, ltp=120.25, ltq=75, ltt=111,
                                              atp=118.0, volume=90000, oi=500000,
                                              depth=[LVL])))
    a.on_packet(P.decode_packet(P.encode_prev_close(P.NSE_FNO, 1, 110.0, 480000)))
    a.on_packet(P.decode_packet(P.encode_full(P.NSE_FNO, 2, ltp=60.0, ltq=75, ltt=112, atp=61,
                                              volume=70000, oi=300000)))
    a.on_packet(P.decode_packet(P.encode_oi(P.NSE_FNO, 4, 1000)))   # OI only, no trade yet
    a.on_packet(P.decode_packet(P.encode_oi(P.NSE_FNO, 777, 1)))    # not ours
    return a


def test_snapshot_is_vendor_raw_and_none_when_missing():
    a = _fed()
    snap = a.snapshot(dt.datetime(2026, 10, 19, 4, 0, tzinfo=UTC))
    assert a.unknown_packets == 1
    es = snap.get("NIFTY", EXP)
    assert es.spot == pytest.approx(25050.0)
    assert [s.strike for s in es.strikes] == [25000.0, 25100.0]
    ce = es.strikes[0].ce
    assert ce.ltp == pytest.approx(120.25) and ce.volume == 90000 and ce.oi == 500000
    assert ce.bid == pytest.approx(120.0) and ce.ask == pytest.approx(120.5) and ce.bid_qty == 750
    assert ce.prev_close == pytest.approx(110.0) and ce.prev_oi == 480000
    assert ce.last_packet_at == 1000.0 and ce.packets == 2
    k2 = es.strikes[1]
    assert k2.ce.ltp is None and k2.ce.oi is None and k2.ce.bid is None   # never received
    assert k2.pe.oi == 1000 and k2.pe.ltp is None and k2.pe.volume is None
    assert es.call_oi_total == 500000 and es.put_oi_total == 301000
    assert es.future is not None and es.future.ltp is None
    assert snap.index["NIFTY"].ltp == pytest.approx(25050.0)


def test_quote_mode_leg_has_no_depth():
    meta = ContractMeta(P.BSE_FNO, 5, "SENSEX", "CE", EXP, 82000.0)
    a = ChainAssembler([meta])
    a.on_packet(P.decode_packet(P.encode_quote(P.BSE_FNO, 5, ltp=300.0, ltq=20, ltt=1, atp=299,
                                               volume=400)))
    a.on_packet(P.decode_packet(P.encode_oi(P.BSE_FNO, 5, 2500)))
    leg = a.snapshot().get("SENSEX", EXP).strikes[0].ce
    assert leg.ltp == pytest.approx(300.0) and leg.oi == 2500 and leg.depth is None
    assert leg.bid is None and leg.ask is None


def test_minute_snapshotter_emits_at_minute_closes_in_session():
    a = _fed()
    # 09:15:30 IST = 03:45:30 UTC
    t = [dt.datetime(2026, 10, 19, 3, 45, 30, tzinfo=UTC).timestamp()]

    async def sleep(s):
        t[0] += s

    got = []
    snapper = MinuteSnapshotter(a, got.append, clock=lambda: t[0], sleep=sleep)
    asyncio.run(snapper.run(max_snapshots=3))
    ist = [s.at.astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime("%H:%M:%S")
           for s in got]
    assert ist == ["09:16:00", "09:17:00", "09:18:00"]
    assert got[0].get("NIFTY", EXP).strikes[0].ce.oi == 500000


def test_minute_snapshotter_skips_pre_open_and_iterates():
    a = _fed()
    t = [dt.datetime(2026, 10, 19, 3, 43, 30, tzinfo=UTC).timestamp()]   # 09:13:30 IST

    async def sleep(s):
        t[0] += s
        await asyncio.sleep(0)

    snapper = MinuteSnapshotter(a, clock=lambda: t[0], sleep=sleep)

    async def main():
        out = []

        async def consume():
            async for snap in snapper:
                out.append(snap.at)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        await snapper.run(max_snapshots=2)
        await task
        return out

    out = asyncio.run(asyncio.wait_for(main(), 5))
    # 09:14 and 09:15 closes are pre-open; first emitted close is 09:16 IST (03:46 UTC)
    assert [x.strftime("%H:%M") for x in out] == ["03:46", "03:47"]


def test_minute_snapshotter_last_close_is_1530():
    a = _fed()
    t = [dt.datetime(2026, 10, 19, 9, 58, 30, tzinfo=UTC).timestamp()]   # 15:28:30 IST
    got = []

    async def sleep(s):
        t[0] += s
        if t[0] > dt.datetime(2026, 10, 19, 10, 5, tzinfo=UTC).timestamp():
            snapper.stop()
        await asyncio.sleep(0)

    snapper = MinuteSnapshotter(a, got.append, clock=lambda: t[0], sleep=sleep)
    asyncio.run(asyncio.wait_for(snapper.run(), 5))
    assert [s.at.strftime("%H:%M") for s in got] == ["09:59", "10:00"]   # 15:29, 15:30 IST


def test_universe_from_scrip_master():
    path = os.path.join(os.path.dirname(__file__), "fixtures", "dhan_scrip_master_sample.csv")
    insts = parse_scrip_master(open(path).read())
    u = near_expiry_universe(insts, ["NIFTY", "SENSEX"], 5, today=dt.date(2026, 10, 19))
    assert u.expiries["NIFTY"][0] == dt.date(2026, 10, 19) and len(u.expiries["NIFTY"]) == 5
    assert len(u.expiries["SENSEX"]) == 2
    assert u.option_count == 5 * 4 + 2 * 4
    kinds = {(c.underlying, c.option_type) for c in u.contracts}
    assert ("NIFTY", "INDEX") in kinds and ("SENSEX", "INDEX") in kinds and ("NIFTY", "FUT") in kinds
    idx = {c.underlying: c.security_id for c in u.contracts if c.option_type == "INDEX"}
    assert idx == {"NIFTY": 13, "SENSEX": 51}
    modes = {(f.segment, f.resolved_mode) for f in u.feed}
    assert modes == {(P.IDX_I, "ticker"), (P.NSE_FNO, "full"), (P.BSE_FNO, "quote")}
    assert len(u.feed) == len(u.contracts)
