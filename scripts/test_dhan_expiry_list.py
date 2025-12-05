import os
from dhanhq import dhanhq
import inspect

client_id = os.getenv("DHAN_CLIENT_ID")
access_token = os.getenv("DHAN_ACCESS_TOKEN")

if not client_id or not access_token:
    print("Please set credentials")
    exit(1)

dhan = dhanhq(client_id, access_token)

# Check if expiry_list method exists
print("Checking for expiry_list method...")
for name in dir(dhan):
    if 'expiry' in name.lower():
        print(f"  - {name}")
        try:
            method = getattr(dhan, name)
            if callable(method):
                sig = inspect.signature(method)
                print(f"    Signature: {sig}")
        except Exception as e:
            print(f"    Error: {e}")

# Try to call it
print("\nTrying to fetch NIFTY expiry list...")
try:
    result = dhan.expiry_list(under_security_id="13", under_exchange_segment="IDX_I")
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
