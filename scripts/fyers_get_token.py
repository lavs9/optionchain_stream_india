"""
Quick Fyers Access Token Generator
"""

from fyers_apiv3 import fyersModel
import os
import sys

# Credentials — read from env, never hardcode
APP_ID = os.getenv("FYERS_CLIENT_ID")
SECRET_ID = os.getenv("FYERS_SECRET_ID")
REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")

# Auth code — one-time, from the Fyers OAuth redirect; pass as first CLI arg
AUTH_CODE = sys.argv[1] if len(sys.argv) > 1 else os.getenv("FYERS_AUTH_CODE")

if not all([APP_ID, SECRET_ID, REDIRECT_URI, AUTH_CODE]):
    sys.exit(
        "Set FYERS_CLIENT_ID, FYERS_SECRET_ID, FYERS_REDIRECT_URI env vars, "
        "and pass the auth code as the first argument (or FYERS_AUTH_CODE env var)."
    )

try:
    # Create session
    session = fyersModel.SessionModel(
        client_id=APP_ID,
        secret_key=SECRET_ID,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code"
    )
    
    # Set auth code
    session.set_token(AUTH_CODE)
    
    # Generate access token
    print("Generating access token...")
    response = session.generate_token()
    
    print("\n" + "=" * 80)
    print("RESPONSE")
    print("=" * 80)
    print(response)
    print()
    
    if response and 'access_token' in response:
        access_token = response['access_token']
        print("\n" + "=" * 80)
        print("✅ ACCESS TOKEN GENERATED!")
        print("=" * 80)
        print(f"\n{access_token}\n")
        print("=" * 80)
        print()
        print("Save this as:")
        print(f'export FYERS_CLIENT_ID="{APP_ID}"')
        print(f'export FYERS_ACCESS_TOKEN="{access_token}"')
        print()
    else:
        print("\n❌ Failed to generate access token")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
