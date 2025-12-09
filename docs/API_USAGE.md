# API Usage Patterns

This document explains the two main patterns for retrieving option chain data: **Polling** (REST API) and **Streaming** (WebSocket).

## Overview

| Pattern | Method | Use Case | Data Freshness | Resource Usage |
|---------|--------|----------|----------------|----------------|
| **Polling** | `fetch_option_chain()` | Complete snapshots at intervals | 3-5 seconds | Higher (repeated full fetches) |
| **Streaming** | `subscribe() + on_tick()` | Real-time updates for specific instruments | <1 second | Lower (only updates) |

---

## Pattern 1: Option Chain Polling

### When to Use
- Need **complete option chain** with all strikes
- Want **all data fields** (OI, Volume, Greeks, etc.)
- Acceptable **3-5 second** update interval
- Building dashboards or analytics

### How It Works
```python
from optionchain_stream.brokers.fyers_broker import FyersBroker

# Initialize broker
broker = FyersBroker(
    client_id="YOUR_CLIENT_ID",
    access_token="YOUR_ACCESS_TOKEN"
)

# Fetch complete option chain
option_chain = broker.fetch_option_chain(
    symbol="NIFTY",
    expiry="2025-12-09"
)

# Response includes:
# - data: List of all option contracts (CE + PE)
# - spot_price: Underlying index price  
# - pcr: Put-Call Ratio
# - Complete fields: LTP, OI, Volume, Bid/Ask, Changes%, etc.
```

### Polling Example with Interval
```python
import time

def poll_option_chain(broker, symbol, expiry, interval=5):
    """Poll option chain at regular intervals"""
    while True:
        try:
            data = broker.fetch_option_chain(symbol, expiry)
            
            # Process data
            print(f"Spot: {data['spot_price']}, PCR: {data['pcr']:.2f}")
            print(f"Contracts: {len(data['data'])}")
            
            time.sleep(interval)  # Wait before next poll
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(interval)

# Usage
poll_option_chain(broker, "NIFTY", "2025-12-09", interval=5)
```

### Rate Limits & Best Practices

#### Fyers
- **Endpoint**: `optionchain()` API
- **Rate Limit**: Not explicitly documented, recommended 3-5 seconds
- **Strikes**: Up to 50 on each side (CE/PE)
- **Fields**: 25+ including OI changes, LTP changes, Bid/Ask
- **Best Practice**: Poll every 5 seconds during market hours

#### Dhan
- Re-check logs for response after December 9, 2025
#### Upstox
- **Endpoint**: Option chain REST API
- **Rate Limit**: 250 requests/second (account-wide)
- **Best Practice**: Poll every 3-5 seconds per symbol

### Advantages
✅ Complete data with all strikes  
✅ All fields available (not limited like WebSocket)  
✅ Simpler to implement  
✅ No connection management needed  
✅ Works well for dashboards

### Disadvantages
❌ Higher latency (3-5 seconds minimum)  
❌ More bandwidth usage  
❌ May hit rate limits if polling too frequently  
❌ Not suitable for tick-by-tick trading

---

## Pattern 2: WebSocket Streaming

### When to Use
- Need **real-time** updates (<1 second)
- Monitoring **specific strikes** (not entire chain)
- Building trading algorithms
- Need tick-by-tick price updates

### How It Works
```python
from optionchain_stream.brokers.fyers_broker import FyersBroker

broker = FyersBroker(client_id="XXX", access_token="YYY")

# Define callback for incoming ticks
def handle_tick(ticks):
    for tick in ticks:
        print(f"{tick.symbol}: LTP={tick.last_price}, Vol={tick.volume}, OI={tick.oi}")

# Register callback
broker.on_tick(handle_tick)

# Subscribe to specific instruments
broker.subscribe([
    "NSE:NIFTY25D0925900CE",  # Specific call option
    "NSE:NIFTY25D0925900PE",  # Specific put option
], mode="full")

# Start WebSocket connection (blocking)
broker.connect()
```

### Streaming with Background Thread
```python
import threading

def start_streaming_background(broker, symbols):
    """Run WebSocket in background thread"""
    
    def stream_worker():
        broker.on_tick(lambda ticks: process_ticks(ticks))
        broker.subscribe(symbols, mode="full")
        broker.connect()
    
    thread = threading.Thread(target=stream_worker, daemon=True)
    thread.start()
    return thread

def process_ticks(ticks):
    """Process incoming tick data"""
    for tick in ticks:
        # Update your data store, trigger alerts, etc.
        pass

# Usage
symbols = ["NSE:NIFTY25D0925900CE", "NSE:NIFTY25D0925900PE"]
thread = start_streaming_background(broker, symbols)

# Main thread continues...
# thread.join()  # Wait for streaming to complete
```

### Rate Limits & Best Practices

#### Fyers
- **Max Connections**: 5 simultaneous connections per account
- **Max Symbols**: 50 symbols per subscription
- **Reconnection**: Automatic with exponential backoff
- **Best Practice**: Subscribe only to strikes you actively need

#### Dhan
- **Max Connections**: 1 connection per account
- **Max Instruments**: 100 instruments per connection
- **Message Rate**: No strict limit documented
- **Best Practice**: Use single connection for all subscriptions

#### Upstox
- **Max Connections**: 3 simultaneous connections
- **Max Symbols**: 500 symbols per WebSocket
- **Data Modes**: `ltpc` (basic) or `full` (complete)
- **Best Practice**: Use `ltpc` mode if you don't need OI/Volume

### WebSocket Data Fields

**Limited compared to polling:**
- ✅ LTP (Last Traded Price)
- ✅ Volume
- ✅ OI (Open Interest)
- ✅ Bid/Ask (in full mode)
- ❌ No OI changes %
- ❌ No LTP changes %
- ❌ No Greeks
- ❌ No historical data

### Advantages
✅ Real-time updates (<1 second)  
✅ Low latency for trading  
✅ Efficient bandwidth usage  
✅ Only updates changed values  
✅ Perfect for tick-by-tick monitoring

### Disadvantages
❌ Limited to subscribed instruments only  
❌ Fewer data fields than polling  
❌ Connection management required  
❌ Rate limits on connections  
❌ Need reconnection logic

---

## Hybrid Approach (Recommended)

Combine both patterns for optimal results:

```python
import threading
import time

class HybridOptionChainMonitor:
    def __init__(self, broker, symbol, expiry):
        self.broker = broker
        self.symbol = symbol
        self.expiry = expiry
        self.option_chain_data = {}
        self.live_prices = {}
    
    def start(self):
        """Start both polling and streaming"""
        # Thread 1: Poll complete option chain every 10 seconds
        threading.Thread(
            target=self._poll_worker,
            daemon=True
        ).start()
        
        # Thread 2: Stream ATM strikes for real-time prices
        threading.Thread(
            target=self._stream_worker,
            daemon=True
        ).start()
    
    def _poll_worker(self):
        """Poll complete option chain periodically"""
        while True:
            try:
                self.option_chain_data = self.broker.fetch_option_chain(
                    self.symbol,
                    self.expiry
                )
                print(f"Polled: {len(self.option_chain_data['data'])} contracts")
                time.sleep(10)  # Poll every 10 seconds
            except:
                time.sleep(10)
    
    def _stream_worker(self):
        """Stream ATM strikes for real-time updates"""
        spot = self.option_chain_data.get('spot_price', 26000)
        atm_strike = round(spot / 50) * 50
        
        # Subscribe to ATM ±2 strikes (10 options total)
        symbols = []
        for strike in range(atm_strike - 100, atm_strike + 150, 50):
            symbols.append(f"NSE:NIFTY25D09{strike}CE")
            symbols.append(f"NSE:NIFTY25D09{strike}PE")
        
        self.broker.on_tick(self._handle_tick)
        self.broker.subscribe(symbols, mode="full")
        self.broker.connect()
    
    def _handle_tick(self, ticks):
        """Update live prices from stream"""
        for tick in ticks:
            self.live_prices[tick.symbol] = {
                'ltp': tick.last_price,
                'volume': tick.volume,
                'oi': tick.oi
            }

# Usage
monitor = HybridOptionChainMonitor(broker, "NIFTY", "2025-12-09")
monitor.start()
```

**Benefits of Hybrid:**
- Full option chain data from polling
- Real-time ATM strike updates from streaming
- Best of both worlds

---

## Choosing the Right Pattern

| Requirement | Recommended Pattern |
|-------------|---------------------|
| Dashboard showing full chain | **Polling** (5 sec interval) |
| Trading bot for specific strikes | **Streaming** |
| Analytics / Research | **Polling** (10 sec interval) |
| Scalping / HFT | **Streaming** |
| Multi-symbol monitoring | **Hybrid** (poll all, stream ATM) |
| Historical snapshots | **Polling** with storage |

---

## API Documentation Links

For detailed rate limits and API specifications:
- [Fyers API Documentation](https://myapi.fyers.in/docsv3)
- [Dhan API Documentation](https://dhanhq.co/docs/v1/)
- [Upstox API Documentation](https://upstox.com/developer/api-documentation)

See [BROKER_APIS.md](BROKER_APIS.md) for direct links to specific endpoints.
