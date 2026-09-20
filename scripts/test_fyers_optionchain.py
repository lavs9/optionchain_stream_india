"""
Test Fyers Option Chain Fetching
"""

import os
import sys
import logging
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.brokers.fyers_broker import FyersBroker

logging.basicConfig(level=logging.INFO)

# Credentials
CLIENT_ID = os.getenv("FYERS_CLIENT_ID")
ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN")
if not CLIENT_ID or not ACCESS_TOKEN:
    sys.exit("Set FYERS_CLIENT_ID and FYERS_ACCESS_TOKEN environment variables before running this script.")

print("=" * 80)
print("FYERS OPTION CHAIN TEST")
print("=" * 80)
print()

# Initialize broker
print("Initializing Fyers broker...")
broker = FyersBroker(client_id=CLIENT_ID, access_token=ACCESS_TOKEN)

# Get available expiries
print("Fetching available expiries for NIFTY...")
provider = broker.get_instrument_provider()
instruments = provider.fetch_instruments()

nifty_expiries = set()
for inst in instruments:
    if "NIFTY" in inst.symbol and inst.instrument_type in ["CE", "PE"] and inst.expiry:
        nifty_expiries.add(inst.expiry.strftime("%Y-%m-%d"))

print(f"\nAvailable NIFTY expiries (showing first 5):")
sorted_expiries = sorted(list(nifty_expiries))[:5]
for expiry in sorted_expiries:
    print(f"  - {expiry}")

if sorted_expiries:
    # Test with nearest expiry
    test_expiry = sorted_expiries[0]
    
    print(f"\n\nTesting option chain fetch for NIFTY expiry: {test_expiry}")
    print("-" * 80)
    
    option_chain = broker.fetch_option_chain("NIFTY", test_expiry)
    
    if option_chain and option_chain.get('data'):
        data = option_chain['data']
        print(f"✅ Successfully fetched option chain!")
        print(f"Number of option contracts: {len(data)}")
        print(f"\nFirst 5 strikes:")
        for item in data[:5]:
            print(f"  Strike {item['strike_price']} {item['option_type']}: {item['symbol']}")
        
        print(f"\n\nFull response structure:")
        print(json.dumps({
            'spot_price': option_chain.get('spot_price'),
            'pcr': option_chain.get('pcr'),
            'symbol': option_chain.get('symbol'),
            'expiry': option_chain.get('expiry'),
            'total_contracts': len(data)
        }, indent=2))
    else:
        print("❌ Failed to fetch option chain")
        print(f"Response: {option_chain}")
else:
    print("\n❌ No NIFTY expiries found")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
