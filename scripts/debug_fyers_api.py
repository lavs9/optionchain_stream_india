"""
Debug Fyers option chain API response
"""

from fyers_apiv3 import fyersModel
from datetime import datetime
import json

CLIENT_ID = "287HSZ2173-100"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIl0sImF0X2hhc2giOiJnQUFBQUFCcE5sUnRkMjdKM0RJNFBxTExZUnRLTlVJRUxlaUtyRV9EWGUxM3I2VHBnSkpSMlM2Y3RGRXZhWF84Ti0wdmxvdzNVRFFrSnFHSmZGS0t6UWNBZXVEb1dfNlc3WXdVZy1aa2hlVGktd203eDJpUHBYWT0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiIyNGI0ZTY0NzYxYWJmOTc5NjdhMjg2MGU4YjkxMGIyMTZlM2FkOWEyOGRmOGZkNjYzY2RlN2U5NiIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiRkFBMTc1ODMiLCJhcHBUeXBlIjoxMDAsImV4cCI6MTc2NTI0MDIwMCwiaWF0IjoxNzY1MTY4MjM3LCJpc3MiOiJhcGkuZnllcnMuaW4iLCJuYmYiOjE3NjUxNjgyMzcsInN1YiI6ImFjY2Vzc190b2tlbiJ9.q6D_4Pmrx_W9XZU7h8AYZZayMXyQQ6SJHt-08KDRap0"

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

