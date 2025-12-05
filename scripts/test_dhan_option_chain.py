import os
import logging
import sys
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.brokers.dhan_broker import DhanBroker

# Configure logging
logging.basicConfig(level=logging.INFO)

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

    # First, find valid expiry dates from instrument master
    print("\nFinding valid expiry dates from instrument master...")
    provider = broker.get_instrument_provider()
    instruments = provider.fetch_instruments()
    
    # Find NIFTY option expiries
    nifty_expiries = set()
    for inst in instruments:
        if "NIFTY" in inst.symbol and inst.instrument_type == "OPTIDX" and inst.expiry:
            nifty_expiries.add(inst.expiry.strftime("%Y-%m-%d"))
    
    # Find BANKNIFTY option expiries
    banknifty_expiries = set()
    for inst in instruments:
        if "BANKNIFTY" in inst.symbol and inst.instrument_type == "OPTIDX" and inst.expiry:
            banknifty_expiries.add(inst.expiry.strftime("%Y-%m-%d"))
    
    print(f"NIFTY Expiries (showing first 3): {sorted(nifty_expiries)[:3]}")
    print(f"BANKNIFTY Expiries (showing first 3): {sorted(banknifty_expiries)[:3]}")
    
    # Use nearest expiry
    nifty_expiry = sorted(nifty_expiries)[0] if nifty_expiries else "2025-12-31"
    banknifty_expiry = sorted(banknifty_expiries)[0] if banknifty_expiries else "2025-12-31"

    # Test with NIFTY
    print("\n" + "="*80)
    print("Testing Option Chain Polling for NIFTY")
    print("="*80)
    
    print(f"\nFetching option chain for NIFTY, expiry: {nifty_expiry}")
    option_chain = broker.fetch_option_chain("NIFTY", nifty_expiry)
    
    if option_chain and option_chain.get('data'):
        if isinstance(option_chain['data'], list) and len(option_chain['data']) > 0:
            print(f"\n✅ Successfully fetched option chain!")
            print(f"Number of option contracts: {len(option_chain['data'])}")
            print("\n📊 Sample Option Data (first item):")
            print(json.dumps(option_chain['data'][0], indent=2)[:1000] + "...")
        else:
            print(f"Empty data")
    else:
        print(f"No data")
        if option_chain:
            print(f"Response: {option_chain}")

    # Test with BANKNIFTY
    print("\n" + "="*80)
    print("Testing Option Chain Polling for BANKNIFTY")
    print("="*80)
    
    print(f"\nFetching option chain for BANKNIFTY, expiry: {banknifty_expiry}")
    option_chain = broker.fetch_option_chain("BANKNIFTY", banknifty_expiry)
    
    if option_chain and option_chain.get('data'):
        if isinstance(option_chain['data'], list) and len(option_chain['data']) > 0:
            print(f"\n✅ Successfully fetched option chain!")
            print(f"Number of option contracts: {len(option_chain['data'])}")
            print("\n📊 Sample Option Data (first item):")
            print(json.dumps(option_chain['data'][0], indent=2)[:1000] + "...")
        else:
            print(f"Empty data")
    else:
        print(f"No data")

if __name__ == "__main__":
    main()
