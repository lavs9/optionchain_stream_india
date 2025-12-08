"""
Fyers Authentication Helper

Generates access token for Fyers API using OAuth 2.0 flow.

Usage:
    python scripts/fyers_auth.py

This script will:
1. Generate login URL
2. Wait for you to authorize and get auth code
3. Generate access token using the auth code
"""

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fyers_apiv3 import fyersModel

# Your Fyers credentials
APP_ID = "287HSZ2173-100"
SECRET_ID = "8CFHG0D64R"
REDIRECT_URI = "https://webhook.site/f5dee680-2a7f-4052-b807-1cc98af79083"

def generate_auth_url():
    """Generate the authorization URL for Fyers login"""
    # Create session object
    session = fyersModel.SessionModel(
        client_id=APP_ID,
        secret_key=SECRET_ID,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code"
    )
    
    # Generate auth code URL
    auth_url = session.generate_authcode()
    
    return auth_url, session

def generate_access_token(auth_code: str):
    """Generate access token using auth code"""
    session = fyersModel.SessionModel(
        client_id=APP_ID,
        secret_key=SECRET_ID,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code"
    )
    
    # Set the authorization code
    session.set_token(auth_code)
    
    # Generate access token
    response = session.generate_token()
    
    return response

def main():
    print("=" * 80)
    print("FYERS AUTHENTICATION HELPER")
    print("=" * 80)
    print()
    print("Credentials:")
    print(f"  App ID: {APP_ID}")
    print(f"  Redirect URI: {REDIRECT_URI}")
    print()
    
    # Step 1: Generate auth URL
    print("STEP 1: Generate Authorization URL")
    print("-" * 80)
    auth_url, session = generate_auth_url()
    print(f"\n✅ Authorization URL generated!")
    print(f"\n{auth_url}\n")
    
    # Step 2: User authorization
    print("STEP 2: Authorize Application")
    print("-" * 80)
    print("1. Open the URL above in your browser")
    print("2. Login with your Fyers credentials")
    print("3. Authorize the application")
    print("4. You'll be redirected to the webhook URL")
    print("5. Copy the 'auth_code' parameter from the redirect URL")
    print()
    print("Example redirect URL:")
    print(f"  {REDIRECT_URI}?auth_code=YOUR_AUTH_CODE&state=sample_state")
    print()
    
    # Get auth code from user
    auth_code = input("Enter the auth_code from redirect URL: ").strip()
    
    if not auth_code:
        print("\n❌ No auth code provided. Exiting.")
        return
    
    # Step 3: Generate access token
    print("\nSTEP 3: Generate Access Token")
    print("-" * 80)
    
    try:
        response = generate_access_token(auth_code)
        
        if response and 'access_token' in response:
            access_token = response['access_token']
            
            print("\n✅ Access Token Generated Successfully!")
            print()
            print("=" * 80)
            print("YOUR FYERS ACCESS TOKEN")
            print("=" * 80)
            print(f"\n{access_token}\n")
            print("=" * 80)
            print()
            print("📝 Save this for use in your application:")
            print()
            print("Environment variable:")
            print(f'  export FYERS_CLIENT_ID="{APP_ID}"')
            print(f'  export FYERS_ACCESS_TOKEN="{access_token}"')
            print()
            print("Streamlit secrets (.streamlit/secrets.toml):")
            print("  [fyers]")
            print(f'  client_id = "{APP_ID}"')
            print(f'  access_token = "{access_token}"')
            print()
            print("⚠️  NOTE: Access tokens typically expire daily. You'll need to regenerate.")
            print()
        else:
            print("\n❌ Failed to generate access token")
            print(f"Response: {response}")
            
    except Exception as e:
        print(f"\n❌ Error generating access token: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
