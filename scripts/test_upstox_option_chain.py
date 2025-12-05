import os
import logging
import sys
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.brokers.upstox_broker import UpstoxBroker

# Configure logging
logging.basicConfig(level=logging.INFO)

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

    # First, let's find valid expiry dates from the instrument master
    print("\n" + "="*80)
    print("Finding Valid Expiry Dates")
    print("="*80)
    
    provider = broker.get_instrument_provider()
    instruments = provider.fetch_instruments()
    
    # Find NIFTY option expiries
    nifty_expiries = set()
    for inst in instruments:
        if inst.name == "NIFTY" and inst.instrument_type in ["CE", "PE"] and inst.expiry:
            nifty_expiries.add(inst.expiry.strftime("%Y-%m-%d"))
    
    # Find BANKNIFTY option expiries
    banknifty_expiries = set()
    for inst in instruments:
        if inst.name == "BANKNIFTY" and inst.instrument_type in ["CE", "PE"] and inst.expiry:
            banknifty_expiries.add(inst.expiry.strftime("%Y-%m-%d"))
    
    print(f"\nNIFTY Expiries (showing first 5): {sorted(nifty_expiries)[:5]}")
    print(f"BANKNIFTY Expiries (showing first 5): {sorted(banknifty_expiries)[:5]}")
    
    # Use the nearest expiry
    nifty_expiry = sorted(nifty_expiries)[0] if nifty_expiries else "2025-12-11"
    banknifty_expiry = sorted(banknifty_expiries)[0] if banknifty_expiries else "2025-12-11"

    # Test with NIFTY
    print("\n" + "="*80)
    print("Testing Option Chain Polling for NIFTY")
    print("="*80)
    
    print(f"\nFetching option chain for NIFTY, expiry: {nifty_expiry}")
    option_chain = broker.fetch_option_chain("NIFTY", nifty_expiry)
    
    if option_chain and option_chain.get('data'):
        print(f"\n✅ Successfully fetched option chain!")
        print(f"Response keys: {list(option_chain.keys())}")
        print(f"Number of strikes: {len(option_chain['data'])}")
        
        # Pretty print the first strike
        if option_chain['data']:
            print("\n📊 Sample Strike Data (first item):")
            print(json.dumps(option_chain['data'][0], indent=2, default=str)[:1500] + "...")
    else:
        print("\n❌ Failed to fetch option chain (empty data)")
        print(f"Response: {option_chain}")

    # Test with BANKNIFTY
    print("\n" + "="*80)
    print("Testing Option Chain Polling for BANKNIFTY")
    print("="*80)
    
    print(f"\nFetching option chain for BANKNIFTY, expiry: {banknifty_expiry}")
    option_chain = broker.fetch_option_chain("BANKNIFTY", banknifty_expiry)
    
    if option_chain and option_chain.get('data'):
        print(f"\n✅ Successfully fetched option chain!")
        print(f"Response keys: {list(option_chain.keys())}")
        print(f"Number of strikes: {len(option_chain['data'])}")
        
        # Pretty print the first strike
        if option_chain['data']:
            print("\n📊 Sample Strike Data (first item):")
            print(json.dumps(option_chain['data'][0], indent=2, default=str)[:1500] + "...")
    else:
        print("\n❌ Failed to fetch option chain (empty data)")
        print(f"Response: {option_chain}")

if __name__ == "__main__":
    main()
