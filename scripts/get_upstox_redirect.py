import requests
import os

access_token = os.getenv("UPSTOX_ACCESS_TOKEN")
if not access_token:
    print("UPSTOX_ACCESS_TOKEN not set")
    exit(1)

url = "https://api.upstox.com/v3/feed/market-data-feed"
headers = {
    "Authorization": f"Bearer {access_token}",
    "Accept": "*/*"
}

print(f"Requesting {url}...")
response = requests.get(url, headers=headers, allow_redirects=False)

print(f"Status Code: {response.status_code}")
print(f"Headers: {response.headers}")

if response.status_code == 302:
    print(f"Location: {response.headers.get('Location')}")
else:
    print(f"Response Body: {response.text}")
