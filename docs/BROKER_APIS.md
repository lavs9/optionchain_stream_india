# Broker API Documentation & Rate Limits

This document provides links to official broker API documentation and summarizes key rate limits for option chain streaming.

---

## Fyers

### Official Documentation
- **Main API Docs**: https://myapi.fyers.in/docsv3
- **Option Chain API**: https://myapi.fyers.in/docsv3#tag/Data-Api/paths/~1data~1optionchain/post
- **WebSocket API**: https://myapi.fyers.in/docsv3#tag/Websockets
- **Quotes API**: https://myapi.fyers.in/docsv3#tag/Data-Api/paths/~1data~1quotes/post
- **Authentication**: https://myapi.fyers.in/docsv3#tag/Authorize

### Rate Limits

| Feature | Limit | Notes |
|---------|-------|-------|
| **Option Chain API** | Not explicitly documented | Recommended: 3-5 sec intervals |
| **WebSocket Connections** | 5 simultaneous | Per account |
| **Symbols per WebSocket** | 50 symbols | Per subscription |
| **Quotes API** | 50 symbols per request | Batch quotes |
| **Access Token Validity** | 24 hours | Regenerate daily |

### Important Fields (Option Chain)
```json
{
  "ltp": "Last traded price",
  "oi": "Open interest",
  "oich": "OI change (absolute)",
  "oichp": "OI change %",
  "ltpch": "LTP change (absolute)",
  "ltpchp": "LTP change %",
  "volume": "Volume traded",
  "bid": "Bid price",
  "ask": "Ask price",
  "fyToken": "Unique instrument identifier"
}
```

### Code Example
```python
from fyers_apiv3 import fyersModel

fyers = fyersModel.FyersModel(client_id="XXX-100", is_async=False, token="YYY", log_path="")

# Option Chain
response = fyers.optionchain(data={
    "symbol": "NSE:NIFTY50-INDEX",
    "strikecount": 50,
    "timestamp": ""  # Empty for nearest expiry
})

# Quotes (up to 50 symbols)
quotes = fyers.quotes({"symbols": "NSE:NIFTY25D0925900CE,NSE:NIFTY25D0925900PE"})
```

---

## Dhan

### Official Documentation
- **Main API Docs**: https://dhanhq.co/docs/v1/
- **Market Feed**: https://dhanhq.co/docs/v1/market-feed/
- **WebSocket**: https://dhanhq.co/docs/v1/market-feed/websocket/
- **Market Quote**: https://dhanhq.co/docs/v1/market-feed/market-quote/
- **Authentication**: https://dhanhq.co/docs/v1/authorization/

### Rate Limits

| Feature | Limit | Notes |
|---------|-------|-------|
| **API Requests** | 10 requests/second | Account-wide |
| **WebSocket Connections** | 1 connection | Per account |
| **Instruments per WebSocket** | 100 instruments | Per connection |
| **Market Quote API** | Included in 10 req/sec | Batch up to 100 |
| **Access Token Validity** | Till midnight | Must regenerate daily |

### Important Fields
```json
{
  "LTP": "Last traded price",
  "high": "Day high",
  "low": "Day low",
  "open": "Day open",
  "close": "Previous close",
  "volume": "Volume traded",
  "OI": "Open interest (if derivative)",
  "bidPrice": "Best bid price",
  "askPrice": "Best ask price"
}
```

### Code Example
```python
from dhanhq import dhanhq

dhan = dhanhq("client_id", "access_token")

# Market Quote (up to 100 instruments)
quotes = dhan.marketfeed_quote(
    security_id_list=["52175", "52176"],  # Dhan security IDs
    exchange_segment=dhanhq.FNO
)

# WebSocket
dhan.subscribe_feed([52175, 52176])
```

---

## Upstox

### Official Documentation
- **Main API Docs**: https://upstox.com/developer/api-documentation
- **Option Chain API**: https://upstox.com/developer/api-documentation/market-quote#get-option-chain
- **WebSocket Feed**: https://upstox.com/developer/api-documentation/market-quote#websocket-market-data
- **Market Quotes**: https://upstox.com/developer/api-documentation/market-quote#get-market-quote
- **Authentication**: https://upstox.com/developer/api-documentation/login-flow

### Rate Limits

| Feature | Limit | Notes |
|---------|-------|-------|
| **API Requests** | 250 requests/second | Account-wide |
| **WebSocket Connections** | 3 simultaneous | Per account |
| **Symbols per WebSocket** | 500 symbols | Per connection |
| **Market Quote API** | 250 req/sec | Batch up to 500 symbols |
| **Option Chain API** | Included in rate limit | Returns full chain |
| **Access Token Validity** | 24 hours | Refresh daily |

### Important Fields
```json
{
  "last_price": "LTP",
  "volume": "Volume traded",
  "oi": "Open interest",
  "bid_price": "Best bid",
  "ask_price": "Best ask",
  "ohlc": {
    "open": "Day open",
    "high": "Day high",
    "low": "Day low",
    "close": "Previous close"
  }
}
```

### Code Example
```python
from upstox_client import Configuration, ApiClient, MarketDataApi

config = Configuration()
config.access_token = "YOUR_ACCESS_TOKEN"
api_client = ApiClient(config)
market_data = MarketDataApi(api_client)

# Option Chain
option_chain = market_data.get_option_chain(
    instrument_key="NSE_INDEX|Nifty 50",
    expiry_date="2025-12-09"
)

# Market Quotes (up to 500 symbols)
quotes = market_data.get_full_market_quote(
    symbol="NSE_FO|41295",  # Upstox instrument key
    interval="1d"
)
```

---

## Rate Limit Comparison

| Broker | API Rate | WebSocket Conn | Symbols/WS | Polling Recommendation |
|--------|----------|----------------|------------|------------------------|
| **Fyers** | ~5 sec recommended | 5 | 50 | Every 5 seconds |
| **Dhan** | 10 req/sec | 1 | 100 | Every 3-5 seconds |
| **Upstox** | 250 req/sec | 3 | 500 | Every 3 seconds |

---

## Best Practices

### 1. Respect Rate Limits
```python
import time
from functools import wraps

def rate_limit(calls_per_second):
    """Decorator to enforce rate limiting"""
    min_interval = 1.0 / calls_per_second
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

# Usage
@rate_limit(calls_per_second=0.2)  # Max 1 call per 5 seconds
def fetch_option_chain(broker, symbol, expiry):
    return broker.fetch_option_chain(symbol, expiry)
```

### 2. Handle Connection Errors
```python
def safe_api_call(func, max_retries=3, backoff=2):
    """Retry API calls with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = backoff ** attempt
            print(f"Error: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
```

### 3. Use WebSocket for High-Frequency
If you need updates faster than 3 seconds, use WebSocket:
- Fyers: Max 50 symbols, 5 connections
- Dhan: Max 100 symbols, 1 connection
- Upstox: Max 500 symbols, 3 connections

### 4. Monitor Your Usage
```python
import time

class APIUsageTracker:
    def __init__(self, rate_limit_per_second):
        self.limit = rate_limit_per_second
        self.calls = []
    
    def can_make_call(self):
        now = time.time()
        # Remove calls older than 1 second
        self.calls = [t for t in self.calls if now - t < 1.0]
        return len(self.calls) < self.limit
    
    def record_call(self):
        self.calls.append(time.time())

# Usage
tracker = APIUsageTracker(rate_limit_per_second=10)  # For Dhan

if tracker.can_make_call():
    result = dhan.fetch_option_chain(...)
    tracker.record_call()
else:
    print("Rate limit reached, waiting...")
```

---

## Getting Help

- **Fyers Support**: https://myapi.fyers.in/
- **Dhan Support**: https://dhanhq.co/support
- **Upstox Support**: https://upstox.com/support

For implementation questions, see [API_USAGE.md](API_USAGE.md) for code examples.
