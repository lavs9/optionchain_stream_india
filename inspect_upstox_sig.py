import upstox_client
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3
import inspect

print("MarketDataStreamerV3 Signature:")
try:
    print(inspect.signature(MarketDataStreamerV3.__init__))
except Exception as e:
    print(e)

print("\nMarketDataStreamerV3 Methods:")
for name, method in inspect.getmembers(MarketDataStreamerV3, predicate=inspect.isfunction):
    print(name)
