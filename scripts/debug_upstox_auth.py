import os
import upstox_client

access_token = os.getenv("UPSTOX_ACCESS_TOKEN")
if not access_token:
    print("UPSTOX_ACCESS_TOKEN not set")
    exit(1)

conf = upstox_client.Configuration()
conf.access_token = access_token
api_client = upstox_client.ApiClient(conf)

auth_settings = api_client.configuration.auth_settings()
print(f"Auth Settings: {auth_settings}")

oauth_val = auth_settings.get("OAUTH2", {}).get("value")
print(f"OAUTH2 Value: {oauth_val}")
