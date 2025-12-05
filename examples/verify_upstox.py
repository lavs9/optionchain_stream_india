import os
import logging
import time
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.brokers.upstox_broker import UpstoxBroker
from optionchain_stream.models import Tick

# Configure logging
logging.basicConfig(level=logging.INFO)

def on_tick(ticks):
    for tick in ticks:
        print(f"Received Tick: {tick}")

def main():
    access_token = os.getenv("UPSTOX_ACCESS_TOKEN")
    if not access_token:
        print("Please set UPSTOX_ACCESS_TOKEN environment variable.")
        return

    print("Initializing Upstox Broker...")
    broker = UpstoxBroker(
        client_id=os.getenv("UPSTOX_CLIENT_ID", "dummy_id"),
        client_secret=os.getenv("UPSTOX_CLIENT_SECRET", "dummy_secret"),
        redirect_uri=os.getenv("UPSTOX_REDIRECT_URI", "http://localhost"),
        access_token=access_token
    )

    print("Fetching instruments to find a valid token...")
    provider = broker.get_instrument_provider()
    instruments = provider.fetch_instruments()
    
    # Prioritize NSE Nifty
    target_tokens = []
    for inst in instruments:
        # Look for Nifty 50 Index or Futures
        # Relaxed search: just check symbol or name
        if "NIFTY" in inst.symbol or "NIFTY" in inst.name:
             if inst.exchange == "NSE_INDEX" or inst.exchange == "NSE_FO":
                 target_tokens.append(inst.token)
                 print(f"Found Nifty Token: {inst.token} ({inst.symbol})")
                 if len(target_tokens) >= 1:
                     break
    
    if not target_tokens:
        # Fallback to MCX
        for inst in instruments:
            if inst.exchange == "MCX" and "FUT" in inst.instrument_type:
                 target_tokens.append(inst.token)
                 print(f"Found MCX Token: {inst.token} ({inst.symbol})")
                 if len(target_tokens) >= 5:
                     break
    
    if not target_tokens and instruments:
        target_tokens.append(instruments[0].token)
        print(f"Using first available token: {target_tokens[0]}")

    if target_tokens:
        print(f"Subscribing to {target_tokens}...")
        broker.on_tick(on_tick)
        broker.connect()
        broker.subscribe(target_tokens)
        
        print("Listening for ticks... Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping...")

if __name__ == "__main__":
    main()
