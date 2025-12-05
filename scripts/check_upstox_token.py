import os
import upstox_client
from upstox_client.rest import ApiException

def check_token():
    access_token = os.getenv("UPSTOX_ACCESS_TOKEN")
    if not access_token:
        print("UPSTOX_ACCESS_TOKEN not set")
        return

    print(f"Checking token: {access_token[:10]}...")
    
    conf = upstox_client.Configuration()
    conf.access_token = access_token
    api_client = upstox_client.ApiClient(conf)
    
    try:
        # Try to get user profile
        from upstox_client.api.user_api import UserApi
        user_api = UserApi(api_client)
        response = user_api.get_profile(api_version='2.0')
        print("Token is VALID!")
        print(f"User ID: {response.data.user_id}")
        print(f"User Name: {response.data.user_name}")
        
    except ApiException as e:
        print(f"Token is INVALID or API call failed: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_token()
