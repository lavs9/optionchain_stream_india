"""
Quick Fyers Access Token Generator
"""

from fyers_apiv3 import fyersModel

# Credentials
APP_ID = "287HSZ2173-100"
SECRET_ID = "8CFHG0D64R"
REDIRECT_URI = "https://webhook.site/f5dee680-2a7f-4052-b807-1cc98af79083"

# Auth code from user
AUTH_CODE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIyODdIU1oyMTczIiwidXVpZCI6IjkyNDM0NmM0Njg5NDQ3MzNiYThlMTNjZDYyNTgxYTk5IiwiaXBBZGRyIjoiIiwibm9uY2UiOiIiLCJzY29wZSI6IiIsImRpc3BsYXlfbmFtZSI6IkZBQTE3NTgzIiwib21zIjoiSzEiLCJoc21fa2V5IjoiMjRiNGU2NDc2MWFiZjk3OTY3YTI4NjBlOGI5MTBiMjE2ZTNhZDlhMjhkZjhmZDY2M2NkZTdlOTYiLCJpc0RkcGlFbmFibGVkIjoiTiIsImlzTXRmRW5hYmxlZCI6Ik4iLCJhdWQiOiJbXCJkOjFcIl0iLCJleHAiOjE3NjUxOTgxODMsImlhdCI6MTc2NTE2ODE4MywiaXNzIjoiYXBpLmxvZ2luLmZ5ZXJzLmluIiwibmJmIjoxNzY1MTY4MTgzLCJzdWIiOiJhdXRoX2NvZGUifQ.KPMEL10dpQWt09mYkGruPWhIfc-OBzEv9QPGjKYQdVk"

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
