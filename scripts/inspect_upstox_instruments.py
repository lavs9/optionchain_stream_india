import requests
import gzip
import json

url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
print(f"Fetching {url}...")
response = requests.get(url)
content = gzip.decompress(response.content)
data = json.loads(content)

print(f"Total instruments: {len(data)}")
print("First 5 instruments:")
for item in data[:5]:
    print(item)

print("\nSearching for RELIANCE...")
found = 0
for item in data:
    if item.get('trading_symbol') == 'RELIANCE':
        print(item)
        found += 1
        if found >= 1:
            break
