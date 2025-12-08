"""
Test Fyers Connection and Fetch Option Chain

Simple test script to verify Fyers integration.
"""

import os
import sys
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.brokers.fyers_broker import FyersBroker
from fyers_apiv3 import fyersModel

logging.basicConfig(level=logging.INFO)

# Credentials
CLIENT_ID = "287HSZ2173-100"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIl0sImF0X2hhc2giOiJnQUFBQUFCcE5rZlExektLY3h4cl9MZ3M4Vms3d3p2dTRCd2tDUl93WUdGalotT1Y0dVFxQUZhTmtuZkVPbGpxVEJPaXE2VmhSbDl0RlhMczR5dWtrckUxWEI3bFlFY3hGYnJEYlJTb2xJSk45ZlI4U2xtcHNWUT0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiIyNGI0ZTY0NzYxYWJmOTc5NjdhMjg2MGU4YjkxMGIyMTZlM2FkOWEyOGRmOGZkNjYzY2RlN2U5NiIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiRkFBMTc1ODMiLCJhcHBUeXBlIjoxMDAsImV4cCI6MTc2NTI0MDIwMCwiaWF0IjoxNzY1MTY1MDA4LCJpc3MiOiJhcGkuZnllcnMuaW4iLCJuYmYiOjE3NjUxNjUwMDgsInN1YiI6ImFjY2Vzc190b2tlbiJ9.Q0gaKeWPlQxJQdvUhj-zoEM8MHStCeAjwpEI9QfqT-M"

print("=" * 80)
print("FYERS CONNECTION TEST")
print("=" * 80)
print()

# Test 1: Test basic API connection
print("TEST 1: Testing API Connection")
print("-" * 80)

try:
    # Create Fyers model
    fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=ACCESS_TOKEN, log_path="")
    
    # Test API call - get profile
    print("Fetching profile...")
    profile = fyers.get_profile()
    
    if profile:
        print(f"✅ API Connection Successful!")
        print(f"Response: {profile}")
        print()
    else:
        print(f"❌ Failed to fetch profile")
        print()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# Test 2: Fetch instruments
print("\nTEST 2: Fetching Instruments")
print("-" * 80)

try:
    broker = FyersBroker(client_id=CLIENT_ID, access_token=ACCESS_TOKEN)
    provider = broker.get_instrument_provider()
    
    print("Fetching instruments...")
    instruments = provider.fetch_instruments()
    
    if instruments:
        print(f"✅ Found{len(instruments)} instruments")
        
        # Show some NIFTY options
        nifty_options = [inst for inst in instruments if "NIFTY" in inst.symbol and inst.instrument_type in ["CE", "PE"]][:5]
        
        print(f"\nSample NIFTY options:")
        for inst in nifty_options:
            print(f"  {inst.symbol} - Token: {inst.token}")
        print()
    else:
        print("❌ No instruments found")
        print()
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# Test 3: Check if option chain is available
print("\nTEST 3: Testing Option Chain Support")
print("-" * 80)

try:
    # Check if Fyers has option chain method
    if hasattr(broker, 'fetch_option_chain'):
        print("✅ Option chain method exists")
        print("Note: Fyers may not have native option chain API")
        print("      We may need to build it from instruments")
    else:
        print("⚠️  Option chain method not implemented")
    print()
    
except Exception as e:
    print(f"❌ Error: {e}")
    print()

print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
