# Quick Examples

Ready-to-use code snippets for common tasks.

## Option Chain Polling

### Example 1: Fetch Current Option Chain (Fyers)
```python
from optionchain_stream.brokers.fyers_broker import FyersBroker

# Initialize
broker = FyersBroker(
    client_id="YOUR_CLIENT_ID-100",
    access_token="YOUR_ACCESS_TOKEN"
)

# Get option chain
data = broker.fetch_option_chain("NIFTY", "2025-12-09")

print(f"Spot: ₹{data['spot_price']:.2f}")
print(f"PCR: {data['pcr']:.2f}")
print(f"Contracts: {len(data['data'])}")

# Show ATM strikes
spot = data['spot_price']
for contract in data['data']:
    if abs(contract['strike_price'] - spot) < 200:
        print(f"{contract['option_type']} {contract['strike_price']}: "
              f"LTP={contract['ltp']:.2f}, OI={contract['oi']:,}")
```

### Example 2: Poll with Interval
```python
import time

def monitor_option_chain(interval=5):
    broker = FyersBroker(client_id="XXX", access_token="YYY")
    
    try:
        while True:
            data = broker.fetch_option_chain("NIFTY", "2025-12-09")
            
            # Your logic here
            print(f"Update: Spot={data['spot_price']:.2f}, PCR={data['pcr']:.2f}")
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopped")

monitor_option_chain(interval=5)
```

## WebSocket Streaming

### Example 3: Stream Specific Strikes
```python
from optionchain_stream.brokers.fyers_broker import FyersBroker

broker = FyersBroker(client_id="XXX", access_token="YYY")

# Callback for ticks
def on_tick(ticks):
    for tick in ticks:
        print(f"{tick.symbol}: LTP={tick.last_price}, Vol={tick.volume}")

broker.on_tick(on_tick)

# Subscribe to ATM strikes
broker.subscribe([
    "NSE:NIFTY25D0925900CE",
    "NSE:NIFTY25D0925900PE"
], mode="full")

broker.connect()  # Blocks until disconnected
```

### Example 4: Background Streaming
```python
import threading

def start_background_stream():
    broker = FyersBroker(client_id="XXX", access_token="YYY")
    
    def handle_tick(ticks):
        # Process ticks here
        pass
    
    def stream_worker():
        broker.on_tick(handle_tick)
        broker.subscribe(["NSE:NIFTY25D0925900CE"], mode="full")
        broker.connect()
    
    thread = threading.Thread(target=stream_worker, daemon=True)
    thread.start()
    return thread, broker

thread, broker = start_background_stream()
# Main thread continues...
```

## Redis Caching

### Example 5: Using Instrument Cache
```python
from optionchain_stream.instrument_master.fyers_provider import FyersInstrumentProvider

# First fetch (downloads CSV)
provider = FyersInstrumentProvider()
instruments = provider.fetch_instruments()  # ~10 seconds
print(f"Fetched {len(instruments)} instruments")

# Second fetch (from cache)
instruments = provider.fetch_instruments()  # <100ms
print(f"Cached {len(instruments)} instruments")

# Clear cache if needed
FyersInstrumentProvider.clear_cache()
```

### Example 6: Check Cache Stats
```python
from optionchain_stream.instrument_cache import InstrumentCache

cache = InstrumentCache()
stats = cache.get_stats()

print(f"Backend: {stats['backend']}")  # 'redis' or 'memory'
print(f"TTL: {stats['ttl_seconds']}s")
print(f"Memory keys: {stats['memory_keys']}")
```

## Authentication

### Example 7: Fyers OAuth Flow
```python
# Step 1: Generate auth URL
from fyers_apiv3 import fyersModel

app_id = "YOUR_APP_ID-100"
redirect_uri = "https://webhook.site/YOUR_WEBHOOK"
secret_id = "YOUR_SECRET_ID"

session = fyersModel.SessionModel(
    client_id=app_id,
    redirect_uri=redirect_uri,
    response_type='code',
    state='sample',
    secret_key=secret_id,
    grant_type='authorization_code'
)

# Open this URL in browser
auth_url = session.generate_authcode()
print(f"Visit: {auth_url}")

# Step 2: Get auth code from redirect URL
auth_code = "YOUR_AUTH_CODE_FROM_REDIRECT"

# Step 3: Generate access token
session.set_token(auth_code)
response = session.generate_token()
access_token = response['access_token']

print(f"Access Token: {access_token}")
```

## Hybrid Approach

### Example 8: Combine Polling + Streaming
```python
import threading
import time

class HybridMonitor:
    def __init__(self, broker):
        self.broker = broker
        self.full_chain = {}
        self.live_prices = {}
    
    def start(self):
        # Poll full chain every 10 seconds
        threading.Thread(target=self._poll_loop, daemon=True).start()
        
        # Stream ATM strikes
        threading.Thread(target=self._stream_atm, daemon=True).start()
    
    def _poll_loop(self):
        while True:
            self.full_chain = self.broker.fetch_option_chain("NIFTY", "2025-12-09")
            time.sleep(10)
    
    def _stream_atm(self):
        self.broker.on_tick(lambda ticks: self._update_prices(ticks))
        self.broker.subscribe(["NSE:NIFTY25D0925900CE"], mode="full")
        self.broker.connect()
    
    def _update_prices(self, ticks):
        for tick in ticks:
            self.live_prices[tick.symbol] = tick.last_price

# Usage
monitor = HybridMonitor(broker)
monitor.start()
```

## Error Handling

### Example 9: Rate Limiting
```python
import time
from functools import wraps

def rate_limit(min_interval):
    """Ensure minimum interval between calls"""
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        return wrapper
    return decorator

@rate_limit(min_interval=5.0)  # 5 seconds minimum
def fetch_chain(broker):
    return broker.fetch_option_chain("NIFTY", "2025-12-09")

# Automatically enforces 5-second interval
for _ in range(10):
    data = fetch_chain(broker)
```

### Example 10: Retry with Backoff
```python
import time

def retry_with_backoff(func, max_retries=3, backoff=2):
    """Retry failed API calls"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = backoff ** attempt
            print(f"Error: {e}. Retrying in {wait}s...")
            time.sleep(wait)

# Usage
data = retry_with_backoff(
    lambda: broker.fetch_option_chain("NIFTY", "2025-12-09")
)
```

## Streamlit Demo

### Example 11: Run Demo App
```bash
# Set credentials
export FYERS_CLIENT_ID="YOUR_CLIENT_ID-100"
export FYERS_ACCESS_TOKEN="YOUR_ACCESS_TOKEN"

# Run Streamlit
streamlit run streamlit_demo.py
```

Open http://localhost:8501 and:
1. Select Fyers broker
2. Enter credentials (or use environment variables)
3. Click "Connect"
4. Select NIFTY and expiry
5. Click "Stream Option Chain"

See all 16 columns: OI, Vol, Bid, Ask, LTP, Changes%, IV

---

## More Examples

- **[examples/](examples/)** - Complete working examples
- **[docs/API_USAGE.md](docs/API_USAGE.md)** - Detailed usage patterns
- **[streamlit_demo.py](streamlit_demo.py)** - Full-featured demo app
