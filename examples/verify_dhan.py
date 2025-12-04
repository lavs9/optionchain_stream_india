import os
import logging
import time
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.brokers.dhan_broker import DhanBroker
from optionchain_stream.models import Tick

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
    broker = DhanBroker(client_id, access_token)

    print("Fetching instruments to find a valid token...")
    provider = broker.get_instrument_provider()
    instruments = provider.fetch_instruments()
    
    # Find MCX instrument first (as it might be open late)
    target_tokens = []
    for inst in instruments:
        if inst.exchange == "MCX" and "FUT" in inst.instrument_type:
             target_tokens.append(inst.token)
             print(f"Found MCX Token: {inst.token} ({inst.symbol})")
             if len(target_tokens) >= 5:
                 break
    
    if not target_tokens:
        # Fallback to NSE Nifty
        for inst in instruments:
            if "Nifty 50" in inst.name or "NIFTY 50" in inst.name:
                 if inst.exchange == "NSE_INDEX":
                     target_tokens.append(inst.token)
                     print(f"Found Nifty 50 Token: {inst.token}")
                     break
    
    if not target_tokens and instruments:
        target_tokens.append(instruments[0].token)
        print(f"Using first available token: {target_tokens[0]}")

    if target_tokens:
        print(f"Subscribing to {target_tokens}...")
        broker.on_tick(on_tick)
        broker.connect()
        broker.subscribe(target_tokens)
        
        # Test Option Chain Polling (Placeholder)
        # print("Testing Option Chain Polling...")
        # chain = broker.fetch_option_chain("NIFTY", "2023-10-26")
        # print(f"Option Chain: {chain}")
        
        print("Listening for ticks... Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping...")

if __name__ == "__main__":
    main()
