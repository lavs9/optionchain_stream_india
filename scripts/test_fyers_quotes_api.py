"""
Test Fyers quotes API directly
"""

from fyers_apiv3 import fyersModel
import os
import sys

CLIENT_ID = os.getenv("FYERS_CLIENT_ID")
ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN")
if not CLIENT_ID or not ACCESS_TOKEN:
    sys.exit("Set FYERS_CLIENT_ID and FYERS_ACCESS_TOKEN environment variables before running this script.")

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
