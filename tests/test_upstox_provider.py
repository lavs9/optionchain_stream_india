import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.instrument_master.upstox_provider import UpstoxInstrumentProvider
import logging

logging.basicConfig(level=logging.INFO)

def test_provider():
    provider = UpstoxInstrumentProvider()
    print("Fetching instruments...")
    instruments = provider.fetch_instruments()
    print(f"Fetched {len(instruments)} instruments.")
    
    if instruments:
        print("Sample Instrument:")
        print(instruments[0])
        
        # Check if token is string
        print(f"Token type: {type(instruments[0].token)}")
        assert isinstance(instruments[0].token, str)
        
        # Check lookup
        symbol = instruments[0].symbol
        inst = provider.get_instrument_by_symbol(symbol)
        print(f"Lookup by symbol {symbol}: {inst is not None}")
        
        token = instruments[0].token
        inst = provider.get_instrument_by_token(token)
        print(f"Lookup by token {token}: {inst is not None}")

        # Print unique exchanges
        exchanges = set(i.exchange for i in instruments)
        print(f"Unique Exchanges: {exchanges}")

        # Check for MCX
        mcx_instruments = [i for i in instruments if i.exchange == 'MCX']
        print(f"MCX Instruments count: {len(mcx_instruments)}")
        if mcx_instruments:
            print(f"Sample MCX: {mcx_instruments[0]}")
            print(f"MCX Types: {set(i.instrument_type for i in mcx_instruments)}")

from datetime import date
from optionchain_stream.models import Instrument


def _stock_option_inst(underlying_symbol, expiry_iso, lot_size= 500):
    from datetime import datetime
    return Instrument(
        exchange="NSE_FO",
        token=f"NSE_FO|{underlying_symbol}{expiry_iso}",
        symbol=f"{underlying_symbol} 240 PE {expiry_iso}",
        name=f"{underlying_symbol} COMPANY FULL NAME LTD",  # company name, NOT the underlying symbol
        expiry=datetime.strptime(expiry_iso, "%Y-%m-%d"),
        strike=240.0,
        lot_size=lot_size,
        instrument_type="PE",
        broker_token=f"NSE_FO|x{underlying_symbol}",
        tick_size=0.05,
        underlying_symbol=underlying_symbol,
    )


def test_get_active_expiries_matches_underlying_symbol_for_stocks():
    """Stock F&O options have inst.name == company full name (e.g.
    "CROMPT GREA CON ELEC LTD"), so matching by name misses "CROMPTON".
    Regression: get_active_expiries must match by underlying_symbol."""
    from unittest.mock import patch
    provider = UpstoxInstrumentProvider()
    insts = [
        _stock_option_inst("CROMPTON", "2026-09-29"),
        _stock_option_inst("CROMPTON", "2026-10-29"),
        _stock_option_inst("RELIANCE", "2026-09-29"),
    ]
    with patch.object(provider, "fetch_instruments", return_value=insts):
        expiries = provider.get_active_expiries("CROMPTON")
    assert expiries == ["2026-09-29", "2026-10-29"]


def test_get_lotsize_matches_underlying_symbol_for_stocks():
    from unittest.mock import patch
    provider = UpstoxInstrumentProvider()
    insts = [_stock_option_inst("AMBER", "2026-09-29", lot_size=2500)]
    with patch.object(provider, "fetch_instruments", return_value=insts):
        assert provider.get_lotsize("AMBER") == 2500


def test_get_active_expiries_falls_back_to_name_when_underlying_symbol_empty():
    """Indices / older providers may leave underlying_symbol empty — the
    name-based match must still work for them."""
    from datetime import datetime
    from unittest.mock import patch
    provider = UpstoxInstrumentProvider()
    inst = Instrument(
        exchange="NSE_FO", token="t", symbol="NIFTY PE",
        name="NIFTY", expiry=datetime(2026, 9, 29),
        strike=24000.0, lot_size=75, instrument_type="PE",
        broker_token="t", tick_size=0.05, underlying_symbol="",
    )
    with patch.object(provider, "fetch_instruments", return_value=[inst]):
        assert provider.get_active_expiries("NIFTY") == ["2026-09-29"]


if __name__ == "__main__":
    test_provider()
