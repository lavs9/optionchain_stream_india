from optionchain_stream.instrument_master.fyers_provider import FyersInstrumentProvider
import logging

logging.basicConfig(level=logging.INFO)

def test_provider():
    provider = FyersInstrumentProvider()
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
        
        # Check for MCX
        mcx = [i for i in instruments if i.exchange == 'MCX']
        print(f"MCX Instruments: {len(mcx)}")
        if mcx:
            print(f"Sample MCX: {mcx[0]}")

if __name__ == "__main__":
    test_provider()
