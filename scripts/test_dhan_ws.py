import os
import logging
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.brokers.dhan_broker import DhanBroker

# Configure logging
logging.basicConfig(level=logging.INFO)

def on_tick(ticks):
    for tick in ticks:
        print(f"Received Tick: {tick}")

def main():
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    
    if not client_id or not access_token:
        print("Please set DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN environment variables.")
        return

    print("Initializing Dhan Broker...")
    broker = DhanBroker(
        client_id=client_id,
        access_token=access_token
    )

    print("Fetching instruments to find a valid token...")
    provider = broker.get_instrument_provider()
    instruments = provider.fetch_instruments()
    
    # Find NIFTY instruments
    target_tokens = []
    for inst in instruments:
        # Search for NIFTY 50 index options
        if ("NIFTY" in inst.symbol and 
            inst.exchange == "NSE_FO" and 
            inst.instrument_type in ["OPTIDX", "FUTIDX"]):
            target_tokens.append((inst.token, inst.symbol))
            print(f"Found: {inst.token} - {inst.symbol} ({inst.instrument_type})")
            if len(target_tokens) >= 2:
                break
    
    if not target_tokens:
        print("No NIFTY instruments found")
        return

    # Subscribe to tokens
    tokens = [t[0] for t in target_tokens]
    print(f"\nSubscribing to tokens: {tokens}")
    
    broker.on_tick(on_tick)
    broker.subscribe(tokens, mode="Full")
    
    print("Connecting...")
    try:
        broker.connect()
        
        # Keep running to receive data
        import time
        print("Waiting for market data (15 seconds)...")
        time.sleep(15)
        print("\nStopping...")
        
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
