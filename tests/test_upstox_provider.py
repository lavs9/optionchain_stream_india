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

if __name__ == "__main__":
    test_provider()
