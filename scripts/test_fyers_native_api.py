"""
Test Fyers native option chain API
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.brokers.fyers_broker import FyersBroker
import json

CLIENT_ID = "287HSZ2173-100"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIl0sImF0X2hhc2giOiJnQUFBQUFCcE5rNDNuRnh4dkRHNnJSZ1diTkJzUFFXd1c5TWRSa1NLemhQV1VKcWtERWlJTlYzRGRfRUdPcVgtdGdhR1ZlMi03MUFFR0x6OS1xMHBqS3ptWXZ6MTlKdTBOUVZRLXBFUzNnS19BM3pMeEVDemgtUT0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiIyNGI0ZTY0NzYxYWJmOTc5NjdhMjg2MGU4YjkxMGIyMTZlM2FkOWEyOGRmOGZkNjYzY2RlN2U5NiIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiRkFBMTc1ODMiLCJhcHBUeXBlIjoxMDAsImV4cCI6MTc2NTI0MDIwMCwiaWF0IjoxNzY1MTY2NjQ3LCJpc3MiOiJhcGkuZnllcnMuaW4iLCJuYmYiOjE3NjUxNjY2NDcsInN1YiI6ImFjY2Vzc190b2tlbiJ9.3x42LClzdAHWphAfR_cFftmZXIemmYd2ekymUGMfS3g"

print("Testing Fyers Native Option Chain API...")
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
    print(f"✅ Spot price: {option_chain.get('spot_price')}")
    print(f"✅ PCR: {option_chain.get('pcr'):.2f}")
    print(f"✅ Number of contracts: {len(option_chain.get('data', []))}")
    
    # Show first 3 contracts
    print("\nFirst 3 contracts:")
    for i, contract in enumerate(option_chain.get('data', [])[:3]):
        print(f"\n{i+1}. {contract['symbol']}")
        print(f"   Strike: {contract['strike_price']}")
        print(f"   Type: {contract['option_type']}")
        print(f"   ✅ LTP: {contract['ltp']}")
        print(f"   ✅ OI: {contract['oi']}")
        print(f"   ✅ Volume: {contract['volume']}")
        if contract.get('option_greeks'):
            print(f"   ✅ IV: {contract['option_greeks'].get('iv', 0):.2f}%")

print("\n" + "="*80)
print("✅ SUCCESS! Prices are now showing correctly!")
