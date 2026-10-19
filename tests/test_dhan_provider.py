"""Dhan scrip master parsing (fixture file; no network) + nearest expiries."""
import datetime as dt
import os

import pytest

from optionchain_stream.instrument_master.dhan_provider import (DhanInstrumentProvider,
                                                                 nearest_expiries,
                                                                 parse_scrip_master)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "dhan_scrip_master_sample.csv")
TODAY = dt.date(2026, 10, 19)


@pytest.fixture
def text():
    with open(FIXTURE) as f:
        return f.read()


def test_parse_fields(text):
    insts = parse_scrip_master(text)
    by_id = {i.token: i for i in insts}
    ce = by_id["40005"]   # first live NIFTY expiry, 25000 CE
    assert ce.instrument_type == "CE" and ce.exchange == "NSE_FNO" and ce.exch_id == "NSE"
    assert ce.name == "NIFTY" and ce.underlying_symbol == "NIFTY"
    assert ce.expiry == dt.datetime(2026, 10, 19) and ce.strike == 25000.0 and ce.lot_size == 75
    assert by_id["40006"].instrument_type == "PE"
    fut = next(i for i in insts if i.instrument_type == "FUT")
    assert fut.strike == 0.0 and fut.expiry == dt.datetime(2026, 10, 27)
    idx = by_id["51"]
    assert idx.instrument_type == "INDEX" and idx.exchange == "IDX_I" and idx.exch_id == "BSE"
    assert idx.name == "SENSEX" and idx.expiry is None
    sensex = next(i for i in insts if i.name == "SENSEX" and i.instrument_type == "CE")
    assert sensex.exchange == "BSE_FNO" and sensex.lot_size == 20


def test_underlying_filter(text):
    insts = parse_scrip_master(text, underlyings=["NIFTY", "SENSEX"])
    assert {i.name for i in insts} == {"NIFTY", "SENSEX"}


def test_nearest_expiries(text):
    insts = parse_scrip_master(text)
    got = nearest_expiries(insts, "NIFTY", 5, TODAY)
    assert got == [dt.date(2026, 10, 19), dt.date(2026, 10, 27), dt.date(2026, 11, 3),
                   dt.date(2026, 11, 9), dt.date(2026, 11, 17)]   # expired 10-13 excluded
    assert nearest_expiries(insts, "SENSEX", 5, TODAY) == [dt.date(2026, 10, 22),
                                                            dt.date(2026, 10, 29)]
    assert nearest_expiries(insts, "NIFTY", 0, TODAY) == []


def test_provider_caches_and_looks_up(text):
    calls = []

    def fetch():
        calls.append(1)
        return text

    p = DhanInstrumentProvider(fetch_text=fetch, clock=lambda: 1000.0)
    assert p.get_instrument_by_token(13).name == "NIFTY"
    assert p.get_instrument_by_token("40005").instrument_type == "CE"
    p.fetch_instruments()
    assert len(calls) == 1
    assert p.nearest_expiries("NIFTY", 2, TODAY) == [dt.date(2026, 10, 19), dt.date(2026, 10, 27)]
    assert all(i.exchange == "BSE_FNO" for i in p.fetch_instruments("BSE_FNO"))
    assert p.get_active_expiries("SENSEX", today=TODAY) == ["2026-10-22", "2026-10-29"]
