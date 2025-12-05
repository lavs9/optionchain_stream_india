import os
import logging
from dhanhq import dhanhq

# Configure logging
logging.basicConfig(level=logging.DEBUG)

client_id = os.getenv("DHAN_CLIENT_ID")
access_token = os.getenv("DHAN_ACCESS_TOKEN")

if not client_id or not access_token:
    print("Please set DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN")
    exit(1)

print(f"Client ID: {client_id}")
print(f"Access Token: {access_token[:20]}...")

try:
    print("\nInitializing Dhan client...")
    dhan = dhanhq(client_id, access_token)
    
    print("\nTesting REST API - Getting holdings...")
    holdings = dhan.get_holdings()
    print(f"Holdings response: {holdings}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
