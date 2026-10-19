"""DhanBroker adapter (no network): subscribe from the scrip master, packets -> legacy Tick."""
import os

import pytest

pytest.importorskip("websockets")

from optionchain_stream.brokers.dhan_broker import DhanBroker
from optionchain_stream.dhan import packets as P
from optionchain_stream.instrument_master.dhan_provider import DhanInstrumentProvider

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "dhan_scrip_master_sample.csv")


def _broker():
    text = open(FIXTURE).read()
    prov = DhanInstrumentProvider(fetch_text=lambda: text)
    return DhanBroker("1100001", "tok", instrument_provider=prov)


def test_requires_a_token_source():
    with pytest.raises(ValueError):
        DhanBroker("1100001")


def test_subscribe_and_ticks():
    b = _broker()
    b.subscribe(["13", "40005", "40006", "999999"])
    feed = b.build_feed()
    assert feed.instrument_count == 3
    got = []
    b.on_tick(got.extend)
    b._on_packet(P.decode_packet(P.encode_oi(P.NSE_FNO, 40005, 100)), 0)   # no LTP yet
    assert got == []
    lvl = P.DepthLevel(75, 150, 1, 2, 99.5, 100.5)
    b._on_packet(P.decode_packet(P.encode_full(P.NSE_FNO, 40005, ltp=100.0, ltq=75, ltt=0,
                                               atp=99.0, volume=1500, oi=2000,
                                               depth=[lvl])), 0)
    t = got[-1]
    assert t.token == "40005" and t.last_price == 100.0 and t.oi == 2000 and t.volume == 1500
    assert t.bid_price == 99.5 and t.ask_price == 100.5
    snap = b.assembler.snapshot()
    assert snap.expiries[0].strikes[0].ce.oi == 2000
