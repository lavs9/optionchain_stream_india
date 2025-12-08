"""
Debug full Fyers option chain response structure
"""

from fyers_apiv3 import fyersModel
import json

CLIENT_ID = "287HSZ2173-100"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIl0sImF0X2hhc2giOiJnQUFBQUFCcE5sUnRkMjdKM0RJNFBxTExZUnRLTlVJRUxlaUtyRV9EWGUxM3I2VHBnSkpSMlM2Y3RGRXZhWF84Ti0wdmxvdzNVRFFrSnFHSmZGS0t6UWNBZXVEb1dfNlc3WXdVZy1aa2hlVGktd203eDJpUHBYWT0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiIyNGI0ZTY0NzYxYWJmOTc5NjdhMjg2MGU4YjkxMGIyMTZlM2FkOWEyOGRmOGZkNjYzY2RlN2U5NiIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiRkFBMTc1ODMiLCJhcHBUeXBlIjoxMDAsImV4cCI6MTc2NTI0MDIwMCwiaWF0IjoxNzY1MTY4MjM3LCJpc3MiOiJhcGkuZnllcnMuaW4iLCJuYmYiOjE3NjUxNjgyMzcsInN1YiI6ImFjY2Vzc190b2tlbiJ9.q6D_4Pmrx_W9XZU7h8AYZZayMXyQQ6SJHt-08KDRap0"

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
