"""
Debug full Fyers option chain response structure
"""

from fyers_apiv3 import fyersModel
import json
import os
import sys

CLIENT_ID = os.getenv("FYERS_CLIENT_ID")
ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN")
if not CLIENT_ID or not ACCESS_TOKEN:
    sys.exit("Set FYERS_CLIENT_ID and FYERS_ACCESS_TOKEN environment variables before running this script.")

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=ACCESS_TOKEN, log_path="")

data = {
    "symbol": "NSE:NIFTY50-INDEX",
    "strikecount": 3,  # Just get 3 strikes
    "timestamp": ""
}

print(f"Request: {data}")
print("="*80)

response = fyers.optionchain(data=data)

print("\nFull Response Structure:")
print(json.dumps(response, indent=2))

if response.get('s') == 'ok':
    options_data = response.get('data', {}).get('optionsChain', [])
    print(f"\n\nTotal items in optionsChain: {len(options_data)}")
    
    print("\n\nFirst 10 items:")
    for i, item in enumerate(options_data[:10]):
        print(f"\n{i+1}. Strike: {item.get('strike_price')}, Type: {item.get('option_type')}, Symbol: {item.get('symbol')}")
