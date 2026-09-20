"""
Debug Fyers option chain API response
"""

from fyers_apiv3 import fyersModel
from datetime import datetime
import json
import os
import sys

CLIENT_ID = os.getenv("FYERS_CLIENT_ID")
ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN")
if not CLIENT_ID or not ACCESS_TOKEN:
    sys.exit("Set FYERS_CLIENT_ID and FYERS_ACCESS_TOKEN environment variables before running this script.")

print("Testing Fyers Option Chain API directly...")
print("="*80)

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=ACCESS_TOKEN, log_path="")

# Test with NIFTY
expiry = "2025-12-09"
expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
expiry_dt = expiry_dt.replace(hour=15, minute=30)
expiry_timestamp = str(int(expiry_dt.timestamp()))

# Try different formats
test_cases = [
    {"symbol": "NSE:NIFTY50-INDEX", "strikecount": 10, "timestamp": expiry_timestamp},
    {"symbol": "NSE:NIFTY50-INDEX", "strikecount": 10, "timestamp": ""},  # Empty timestamp
    {"symbol": "NSE:NIFTYBANK-INDEX", "strikecount": 10, "timestamp": ""},  # Try BANKNIFTY
]

for i, data in enumerate(test_cases):
    print(f"\n\nTest {i+1}: {data}")
    print("-"*80)
    
    response = fyers.optionchain(data=data)
    
    print(f"Response status: {response.get('s')}")
    print(f"Response message: {response.get('message', 'N/A')}")
    
    if response and response.get('s') == 'ok':
        print("✅ API call successful!")
        data_obj = response.get('data', {})
        print(f"LTP: {data_obj.get('ltp')}")
        print(f"Options chain length: {len(data_obj.get('optionsChain', []))}")
        
        if data_obj.get('optionsChain'):
            print(f"\nFirst option strike:")
            first_opt = data_obj.get('optionsChain')[0]
            print(json.dumps(first_opt, indent=2))
    else:
        print(f"❌ API call failed!")
        print(f"Full response: {response}")

print("\n" + "="*80)

