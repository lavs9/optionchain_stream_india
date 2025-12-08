"""
Test Fyers quotes API directly
"""

from fyers_apiv3 import fyersModel

CLIENT_ID = "287HSZ2173-100"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIyODdIU1oyMTczIiwidXVpZCI6ImQzZjUxM2I4YTRhMzRiMjc5MzZkNGNlOWM2ODViNTJkIiwiaXBBZGRyIjoiIiwibm9uY2UiOiIiLCJzY29wZSI6IiIsImRpc3BsYXlfbmFtZSI6IkZBQTE3NTgzIiwib21zIjoiSzEiLCJoc21fa2V5IjoiMjRiNGU2NDc2MWFiZjk3OTY3YTI4NjBlOGI5MTBiMjE2ZTNhZDlhMjhkZjhmZDY2M2NkZTdlOTYiLCJpc0RkcGlFbmFibGVkIjoiTiIsImlzTXRmRW5hYmxlZCI6Ik4iLCJhdWQiOiJbXCJkOjFcIl0iLCJleHAiOjE3NjUxOTQ4NjIsImlhdCI6MTc2NTE2NDg2MiwiaXNzIjoiYXBpLmxvZ2luLmZ5ZXJzLmluIiwibmJmIjoxNzY1MTY0ODYyLCJzdWIiOiJhdXRoX2NvZGUifQ.wSLz2EPIe-jGrU9Sl6R9gtdkBZ4hJzZseCdLD6VPHUo"

print("Testing Fyers Quotes API...")
print("="*80)

# Create Fyers model
fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=ACCESS_TOKEN, log_path="")

# Test 1: Get NIFTY index quote
print("\nTest 1: NIFTY50 Index Quote")
print("-"*80)
try:
    response = fyers.quotes({"symbols": "NSE:NIFTY50-INDEX"})
    print(f"Response: {response}")
    
    if response and response.get('s') == 'ok':
        data = response.get('d', {})
        for symbol, quote in data.items():
            print(f"\nSymbol: {symbol}")
            print(f"LTP: {quote.get('v', {}).get('lp')}")
            print(f"Change: {quote.get('v', {}).get('ch')}")
    else:
        print(f"Error: {response}")
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Get option quotes
print("\n\nTest 2: NIFTY Option Quotes")
print("-"*80)
try:
    # Try a few option symbols
    symbols = "NSE:NIFTY25D0920250CE,NSE:NIFTY25D0920250PE,NSE:NIFTY25D0920300CE"
    response = fyers.quotes({"symbols": symbols})
    print(f"Response: {response}")
    
    if response and response.get('s') == 'ok':
        data = response.get('d', {})
        for symbol, quote in data.items():
            print(f"\nSymbol: {symbol}")
            print(f"LTP: {quote.get('v', {}).get('lp')}")
            print(f"OI: {quote.get('v', {}).get('oi')}")
            print(f"Volume: {quote.get('v', {}).get('volume')}")
    else:
        print(f"Error: {response}")
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
