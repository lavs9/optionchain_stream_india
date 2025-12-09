# LLM Guide for Option Chain Streaming India

**For AI Assistants & Language Models**: This document provides structured information to help you understand and use this repository effectively.

## Repository Purpose

This is a **unified multi-broker option chain streaming library** for Indian stock market brokers (Dhan, Upstox, Fyers). It provides:
- Real-time WebSocket streaming for option chains
- REST API polling for option chain snapshots
- Standardized interface across multiple brokers
- Redis-based caching for instrument data

## Quick Navigation for LLMs

### Core Documentation
1. **[README.md](README.md)** - Overview and quick start
2. **[API_USAGE.md](docs/API_USAGE.md)** - Streaming vs Polling patterns
3. **[BROKER_APIS.md](docs/BROKER_APIS.md)** - Broker-specific API documentation links
4. **[EXAMPLES.md](docs/EXAMPLES.md)** - Code examples for common tasks

### Architecture Overview

```
optionchain_stream/
├── broker_interface.py       # Abstract base class for brokers
├── brokers/                   # Broker implementations
│   ├── dhan_broker.py        # Dhan API integration
│   ├── upstox_broker.py      # Upstox API integration
│   └── fyers_broker.py       # Fyers API integration
├── instrument_master/         # Instrument data providers
│   ├── dhan_provider.py      # Dhan instruments (with caching)
│   ├── upstox_provider.py    # Upstox instruments (with caching)
│   └── fyers_provider.py     # Fyers instruments (with caching)
├── instrument_cache.py        # Redis/memory caching layer
└── models.py                  # Data models (Tick, Instrument)
```

## Key Concepts

### 1. Broker Interface
All brokers implement the same interface:
- `fetch_option_chain(symbol, expiry)` - Get option chain snapshot (polling)
- `subscribe(tokens, mode)` - Subscribe to WebSocket stream
- `on_tick(callback)` - Register callback for streaming data
- `connect()` - Start WebSocket connection

### 2. Data Retrieval Modes

#### **Option Chain Polling** (REST API)
- Use `fetch_option_chain(symbol, expiry)`
- Returns complete option chain with all strikes
- **Fyers**: Native `optionchain()` API, 50 strikes each side
- **Dhan**: Custom implementation from quotes
- **Upstox**: REST API endpoint
- **Rate Limits**: See [BROKER_APIS.md](docs/BROKER_APIS.md)

#### **WebSocket Streaming** (Real-time)
- Use `subscribe(tokens)` + `on_tick(callback)` + `connect()`
- Returns only subscribed instruments with live updates
- **Limited fields**: LTP, OI, Volume, Bid/Ask
- **Rate Limits**: Connection limits, message rates per broker

### 3. Instrument Caching
- **Redis-based** with automatic in-memory fallback
- **TTL**: 1 hour (3600 seconds)
- **Why**: Avoids repeated CSV/JSON downloads
- **Performance**: 100x faster after first fetch

## Common Use Cases

### Use Case 1: Poll Complete Option Chain
```python
from optionchain_stream.brokers.fyers_broker import FyersBroker

broker = FyersBroker(client_id="XXX", access_token="YYY")
option_chain = broker.fetch_option_chain("NIFTY", "2025-12-09")

# Returns: {'data': [...], 'spot_price': 26070.5, 'pcr': 1.25}
```

**When to use**: 
- Need complete option chain snapshot
- Want all strikes with full data
- Polling at regular intervals (e.g., every 5 seconds)

### Use Case 2: Stream Specific Options
```python
broker.on_tick(lambda ticks: print(ticks))
broker.subscribe(["NSE:NIFTY25D0925900CE"], mode="full")
broker.connect()  # Blocking call
```

**When to use**:
- Need real-time updates for specific strikes
- Want low-latency price updates
- Monitoring few specific options

## Broker-Specific Information

### Fyers
- **Option Chain API**: Native `optionchain()` method
- **Streaming**: WebSocket (not fully implemented)
- **Columns**: 25+ fields (LTP, OI, Volume, Bid/Ask, OI Chg%, LTP Chg%, etc.)
- **Limits**: See [docs/BROKER_APIS.md - Fyers](docs/BROKER_APIS.md#fyers)

### Dhan  
- **Option Chain API**: Built from instrument list + quotes
- **Streaming**: WebSocket implemented
- **Limits**: See [docs/BROKER_APIS.md - Dhan](docs/BROKER_APIS.md#dhan)

### Upstox
- **Option Chain API**: REST endpoint
- **Streaming**: WebSocket implemented
- **Limits**: See [docs/BROKER_APIS.md - Upstox](docs/BROKER_APIS.md#upstox)

## Important Files for Understanding

1. **`broker_interface.py`** - Start here to understand the contract
2. **`brokers/fyers_broker.py`** - Most complete implementation
3. **`streamlit_demo.py`** - Working example of both modes
4. **`instrument_cache.py`** - Caching mechanism

## Authentication

Each broker requires different credentials:
- **Fyers**: `client_id` + `access_token` (OAuth, daily expiry)
- **Dhan**: `client_id` + `access_token`
- **Upstox**: `client_id` + `client_secret` + `access_token`

See [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) for detailed auth flows.

## Rate Limits & Best Practices

**CRITICAL**: Always check rate limits before implementing:
1. **Polling**: Recommended interval 3-5 seconds minimum
2. **WebSocket**: Max connections, max symbols per subscription
3. **Caching**: Use Redis to avoid hitting instrument API limits

See [docs/BROKER_APIS.md](docs/BROKER_APIS.md) for specific limits.

## Data Structure Reference

### Option Chain Response
```python
{
    'data': [
        {
            'symbol': 'NSE:NIFTY25D0925900CE',
            'strike_price': 25900,
            'option_type': 'CE',  # or 'PE'
            'ltp': 217.55,
            'oi': 1408725,
            'volume': 3774150,
            'bid': 217.3,
            'ask': 217.65,
            'ltpchp': -30.88,  # LTP change %
            'oichp': 61.23,    # OI change %
            # ... more fields
        }
    ],
    'spot_price': 26070.5,
    'pcr': 1.25,  # Put-Call Ratio
    'symbol': 'NIFTY',
    'expiry': '2025-12-09'
}
```

### WebSocket Tick
```python
{
    'token': 'NSE:NIFTY25D0925900CE',
    'ltp': 217.55,
    'volume': 3774150,
    'oi': 1408725,
    'timestamp': datetime(...)
}
```

## Implementation Checklist

When implementing option chain streaming:
- [ ] Choose mode: Polling OR Streaming
- [ ] Check [BROKER_APIS.md](docs/BROKER_APIS.md) for rate limits
- [ ] Implement authentication (see auth examples)
- [ ] Set up Redis for caching (optional but recommended)
- [ ] Handle connection errors and reconnections
- [ ] Implement rate limiting in your code
- [ ] Log API calls for debugging

## Getting Help

1. Check [docs/EXAMPLES.md](docs/EXAMPLES.md) for code samples
2. Review `streamlit_demo.py` for complete working example
3. See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues

## Version Information

- **Python**: 3.8+
- **Dependencies**: See `requirements.txt`
- **Brokers Supported**: Dhan, Upstox, Fyers
- **Last Updated**: 2025-12-09
