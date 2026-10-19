"""Dhan v2 binary packet decoding, from fixtures built with the documented byte layout."""
import datetime as dt
import json
import struct

import pytest

from optionchain_stream.dhan import packets as P

DEPTH = [P.DepthLevel(1500 + i, 900 + i, 12 + i, 9 + i, 101.5 - i * 0.05, 101.6 + i * 0.05)
         for i in range(5)]


def _full():
    return P.encode_full(P.NSE_FNO, 52345, ltp=101.55, ltq=75, ltt=1792405800, atp=99.8,
                         volume=1234500, total_sell_qty=40000, total_buy_qty=42000, oi=987650,
                         oi_day_high=1000000, oi_day_low=950000, day_open=95.0, day_close=0.0,
                         day_high=110.25, day_low=90.5, depth=DEPTH)


def test_full_packet_layout_and_decode():
    raw = _full()
    assert len(raw) == 162
    assert raw[0] == P.RESP_FULL and raw[3] == P.NSE_FNO
    assert struct.unpack_from("<I", raw, 4)[0] == 52345
    pkt = P.decode_packet(raw)
    assert isinstance(pkt, P.FullPacket)
    assert pkt.key == (P.NSE_FNO, 52345)
    assert pkt.ltp == pytest.approx(101.55, abs=1e-4)
    assert (pkt.ltq, pkt.ltt, pkt.volume, pkt.oi) == (75, 1792405800, 1234500, 987650)
    assert (pkt.oi_day_high, pkt.oi_day_low) == (1000000, 950000)
    assert (pkt.total_buy_qty, pkt.total_sell_qty) == (42000, 40000)
    assert pkt.day_high == pytest.approx(110.25) and pkt.day_close == 0.0
    assert len(pkt.depth) == 5
    assert pkt.depth[0].bid_qty == 1500 and pkt.depth[4].ask_orders == 13
    assert pkt.depth[0].bid_price == pytest.approx(101.5, abs=1e-4)


def test_quote_oi_prevclose_ticker_disconnect():
    q = P.decode_packet(P.encode_quote(P.BSE_FNO, 1111, ltp=250.5, ltq=20, ltt=1792405801,
                                       atp=248.0, volume=5000, day_open=240, day_high=260,
                                       day_low=239))
    assert isinstance(q, P.QuotePacket) and q.segment == P.BSE_FNO
    assert (q.ltq, q.volume) == (20, 5000) and q.day_high == pytest.approx(260)
    oi = P.decode_packet(P.encode_oi(P.BSE_FNO, 1111, 77700))
    assert isinstance(oi, P.OIPacket) and oi.oi == 77700
    pc = P.decode_packet(P.encode_prev_close(P.NSE_FNO, 52345, 98.4, 960000))
    assert isinstance(pc, P.PrevClosePacket) and pc.prev_oi == 960000
    assert pc.prev_close == pytest.approx(98.4, abs=1e-4) and len(pc.prev_oi_raw) == 4
    tk = P.decode_packet(P.encode_ticker(P.IDX_I, 13, 25123.45, 1792405802))
    assert isinstance(tk, P.TickerPacket) and tk.ltp == pytest.approx(25123.45, abs=1e-2)
    d = P.decode_packet(P.encode_disconnect(805))
    assert isinstance(d, P.DisconnectPacket) and d.reason == 805 and "5 sockets" in d.reason_text


def test_truncated_and_unknown_packets():
    with pytest.raises(P.PacketError):
        P.decode_packet(_full()[:100])
    with pytest.raises(P.PacketError):
        P.decode_packet(b"\x08\x00")
    unk = P.decode_packet(bytes([99, 8, 0, 2, 1, 0, 0, 0]))
    assert isinstance(unk, P.UnknownPacket) and unk.code == 99


def test_iter_packets_splits_concatenated_frames():
    frame = P.encode_oi(P.NSE_FNO, 1, 10) + P.encode_ticker(P.IDX_I, 13, 1.0, 5) + _full()
    kinds = [type(p).__name__ for p in P.iter_packets(frame)]
    assert kinds == ["OIPacket", "TickerPacket", "FullPacket"]


def test_ltt_to_utc_undoes_ist_epoch_shift():
    # 15:29:00 IST written as if it were UTC epoch
    ist_as_utc = int(dt.datetime(2026, 10, 19, 15, 29, tzinfo=dt.timezone.utc).timestamp())
    got = P.ltt_to_utc(ist_as_utc)
    assert got == dt.datetime(2026, 10, 19, 9, 59, tzinfo=dt.timezone.utc)
    assert P.ltt_to_utc(0) is None


def test_subscribe_messages_batches_of_100():
    keys = [(P.NSE_FNO, 40000 + i) for i in range(250)]
    msgs = P.subscribe_messages(keys, P.REQ_FULL)
    assert len(msgs) == 3
    bodies = [json.loads(m) for m in msgs]
    assert [b["InstrumentCount"] for b in bodies] == [100, 100, 50]
    assert all(b["RequestCode"] == 21 for b in bodies)
    assert bodies[0]["InstrumentList"][0] == {"ExchangeSegment": "NSE_FNO", "SecurityId": "40000"}
    with pytest.raises(ValueError):
        P.subscribe_messages(keys, P.REQ_FULL, per_message=101)


def test_decoder_agrees_with_dhanhq_sdk_struct_layout():
    mf_mod = pytest.importorskip("dhanhq.marketfeed")
    mf = object.__new__(mf_mod.MarketFeed)
    sdk = mf.process_full(_full())
    ours = P.decode_packet(_full())
    assert sdk["security_id"] == ours.security_id and sdk["OI"] == ours.oi
    assert float(sdk["LTP"]) == pytest.approx(ours.ltp, abs=0.01)
    assert sdk["volume"] == ours.volume and sdk["oi_day_low"] == ours.oi_day_low
    assert sdk["depth"][2]["bid_quantity"] == ours.depth[2].bid_qty
    q = P.encode_quote(P.BSE_FNO, 7, ltp=10.0, ltq=1, ltt=100, atp=9.5, volume=42, day_low=8.0)
    sq, oq = mf.process_quote(q), P.decode_packet(q)
    assert sq["volume"] == oq.volume and float(sq["low"]) == pytest.approx(oq.day_low)
    assert mf.process_oi(P.encode_oi(P.BSE_FNO, 7, 55))["OI"] == 55
