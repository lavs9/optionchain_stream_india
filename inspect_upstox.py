import upstox_client
import inspect

print("Upstox Client Dir:")
print(dir(upstox_client))

# Check for specific modules
if hasattr(upstox_client, 'MarketDataFeed'):
    print("\nMarketDataFeed found")
    
if hasattr(upstox_client, 'Websocket'):
    print("\nWebsocket found")

# Try to find anything related to Streamer or Socket
for name in dir(upstox_client):
    if 'Stream' in name or 'Socket' in name or 'Feed' in name:
        print(f"\nPotential Match: {name}")
