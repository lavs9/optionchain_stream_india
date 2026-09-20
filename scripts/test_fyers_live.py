"""
Test Fyers with live credentials to see option chain data
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.brokers.fyers_broker import FyersBroker
import json

CLIENT_ID = os.getenv("FYERS_CLIENT_ID")
ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN")
if not CLIENT_ID or not ACCESS_TOKEN:
    sys.exit("Set FYERS_CLIENT_ID and FYERS_ACCESS_TOKEN environment variables before running this script.")

print("Testing Fyers option chain...")
print("="*80)

broker = FyersBroker(client_id=CLIENT_ID, access_token=ACCESS_TOKEN)

# Get expiries
expiries = broker.get_instrument_provider().fetch_instruments()
nifty_expiries = set()
for inst in expiries:
    if "NIFTY" in inst.symbol and inst.instrument_type in ["CE", "PE"] and inst.expiry:
        nifty_expiries.add(inst.expiry.strftime("%Y-%m-%d"))

expiry_list = sorted(list(nifty_expiries))[:3]
print(f"\nAvailable expiries: {expiry_list}")

if expiry_list:
    test_expiry = expiry_list[0]
    print(f"\nTesting with expiry: {test_expiry}")
    
    option_chain = broker.fetch_option_chain("NIFTY", test_expiry)
    
    print(f"\nOption chain keys: {option_chain.keys()}")
    print(f"Spot price: {option_chain.get('spot_price')}")
    print(f"Number of contracts: {len(option_chain.get('data', []))}")
    
    # Show first 3 contracts
    print("\nFirst 3 contracts:")
    for i, contract in enumerate(option_chain.get('data', [])[:3]):
        print(f"\n{i+1}. {contract['symbol']}")
        print(f"   Strike: {contract['strike_price']}")
        print(f"   Type: {contract['option_type']}")
        print(f"   LTP: {contract['ltp']}")
        print(f"   OI: {contract['oi']}")
        print(f"   Volume: {contract['volume']}")

print("\n" + "="*80)
print("As you can see, LTP/OI/Volume are all 0 - we need to fetch live quotes!")
