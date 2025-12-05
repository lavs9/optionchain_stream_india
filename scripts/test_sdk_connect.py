import os
import logging
import upstox_client
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3

# Configure logging
logging.basicConfig(level=logging.DEBUG)

def on_open():
    print("Opened connection")

def on_message(message):
    print(f"Received message: {message}")

def on_error(error):
    print(f"Error: {error}")

def on_close(code, reason):
    print(f"Closed: {code} {reason}")

if __name__ == "__main__":
    access_token = os.getenv("UPSTOX_ACCESS_TOKEN")
    if not access_token:
        print("UPSTOX_ACCESS_TOKEN not set")
        exit(1)

    print("Initializing SDK...")
    conf = upstox_client.Configuration()
    conf.access_token = access_token
    api_client = upstox_client.ApiClient(conf)
    
    streamer = MarketDataStreamerV3(api_client)
    
    def on_open():
        print("Opened connection")
        # Subscribe to RELIANCE
        streamer.subscribe(["NSE_EQ|INE002A01018"], "full")

    def on_message(message):
        print(f"Received message: {message}")

    streamer.on("open", on_open)
    streamer.on("message", on_message)
    streamer.on("error", on_error)
    streamer.on("close", on_close)
    
    print("Connecting...")
    streamer.connect()
    
    # Keep alive
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Disconnecting...")
        streamer.disconnect()
