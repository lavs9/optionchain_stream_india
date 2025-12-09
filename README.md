# 🚀 Option Chain Stream India

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Enterprise-grade real-time option chain streaming for Indian markets** with multi-broker support, unified data models, and production-ready storage architecture.

> **Credits**: Enhanced fork of [optionchainstream](https://github.com/ranjanrak/optionchainstream) by [ranjanrak](https://github.com/ranjanrak). Built with additional broker support, option chain polling, and multi-broker coordination.

---

## 🤖 For LLMs & AI Assistants

**If you are an AI/LLM helping a developer**: Start with **[LLM_GUIDE.md](LLM_GUIDE.md)** for structured documentation designed specifically for you. It includes:
- Repository architecture and navigation
- Streaming vs Polling decision tree
- Broker-specific rate limits and APIs
- Complete code examples and patterns

**Quick Links for LLMs:**
- **[LLM_GUIDE.md](LLM_GUIDE.md)** - AI-optimized documentation
- **[docs/API_USAGE.md](docs/API_USAGE.md)** - Polling vs Streaming patterns
- **[docs/BROKER_APIS.md](docs/BROKER_APIS.md)** - Rate limits & API links

---

## ✨ Features

### 🔌 Multi-Broker Support
- **Upstox** ✅ (Streaming + Option Chain with Greeks)
- **Dhan** ⚠️ (REST API ready, WebSocket needs subscription)
- **Fyers** 🚧 (SDK integrated, testing in progress)
- **Zerodha Kite** 🚧 (Coming soon)

### 🎯 Core Capabilities
- **Real-time WebSocket Streaming**: Sub-millisecond latency for equities, futures, and options
- **Option Greeks**: Delta, Theta, Vega, Gamma, IV, Probability of Profit
- **Option Chain Polling**: Full snapshots with Greeks for NIFTY, BANKNIFTY
- **Multi-Broker Coordinator**: Bypass subscription limits, run 4000+ instruments
- **Unified Data Model**: Broker-agnostic `Tick` and `Instrument` interfaces
- **Production Storage**: Redis (real-time), ClickHouse (analytics), S3 (archival)

### 🎁 Advanced Features
- **BrokerCoordinator**: Auto-distribute instruments across multiple accounts
- **Hybrid Streaming + Polling**: Real-time for ATM strikes, snapshots for full chain
- **Health Monitoring**: Track connections, subscriptions, tick rates
- **Automatic Reconnection**: Resilient WebSocket handling
- **Thread-Safe**: Concurrent operations with proper synchronization

## 📦 Installation

```bash
# Clone repository
git clone https://github.com/lavs9/optionchain_stream_india.git
cd optionchain_stream_india

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 🔑 Configuration

Set environment variables for your broker(s):

### Upstox
```bash
export UPSTOX_CLIENT_ID="your_client_id"
export UPSTOX_CLIENT_SECRET="your_client_secret"
export UPSTOX_REDIRECT_URI="http://localhost"
export UPSTOX_ACCESS_TOKEN="your_access_token"
```

### Dhan
```bash
export DHAN_CLIENT_ID="your_client_id"
export DHAN_ACCESS_TOKEN="your_access_token"
```

### Fyers
```bash
export FYERS_CLIENT_ID="your_client_id"
export FYERS_ACCESS_TOKEN="your_access_token"
```

### Storage (Optional)
```bash
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export CLICKHOUSE_HOST="localhost"
export CLICKHOUSE_PORT="9000"
```

## 🚀 Quick Start

### Basic Streaming

```python
from optionchain_stream.brokers.upstox_broker import UpstoxBroker
import os

# Initialize broker
broker = UpstoxBroker(
    client_id=os.getenv("UPSTOX_CLIENT_ID"),
    client_secret=os.getenv("UPSTOX_CLIENT_SECRET"),
    redirect_uri="http://localhost",
    access_token=os.getenv("UPSTOX_ACCESS_TOKEN")
)

# Define callback
def on_tick(ticks):
    for tick in ticks:
        print(f"{tick.token}: LTP={tick.last_price}, OI={tick.oi}, Vol={tick.volume}")

# Subscribe and connect
broker.on_tick(on_tick)

# Get NIFTY options
provider = broker.get_instrument_provider()
instruments = provider.fetch_instruments()
nifty_options = [i for i in instruments if "NIFTY" in i.symbol][:10]
tokens = [i.token for i in nifty_options]

broker.subscribe(tokens, mode="full")
broker.connect()
```

### Streamlit Web Demo 🎨

**Try the interactive web interface!**

```bash
# Install dependencies
pip install -r requirements.txt

# Set credentials
export DHAN_CLIENT_ID="your_client_id"
export DHAN_ACCESS_TOKEN="your_access_token"

# Run the demo
streamlit run streamlit_demo.py
```

**Deploy to Streamlit Community Cloud:**
1. Fork this repository
2. Visit [share.streamlit.io](https://share.streamlit.io)
3. Deploy from your GitHub repo
4. Add credentials in Streamlit Cloud Secrets (see [deployment guide](docs/streamlit_demo.md#streamlit-cloud-deployment))

Features:
- 🔄 Multi-broker support (Dhan, Upstox, Fyers)
- 📊 Real-time option chain display
- 📈 Interactive visualizations (IV smile, volume, OI)
- ⚡ Auto-refresh with configurable intervals

[📖 Full Demo Documentation](docs/streamlit_demo.md)

### Option Chain Polling


```python
# Fetch full option chain with Greeks
option_chain = broker.fetch_option_chain("NIFTY", "2025-12-09")

print(f"Spot: {option_chain['spot_price']}")
print(f"PCR: {option_chain['pcr']}")
print(f"Strikes: {len(option_chain['strikes'])}")

for strike in option_chain['strikes'][:5]:
    print(f"\nStrike {strike['strike_price']}:")
    print(f"  Call: LTP={strike['call_options']['ltp']}, "
          f"IV={strike['call_options']['option_greeks']['iv']}")
    print(f"  Put:  LTP={strike['put_options']['ltp']}, "
          f"IV={strike['put_options']['option_greeks']['iv']}")
```

### Multi-Broker Coordinator (Bypass Limits)

```python
from optionchain_stream.broker_coordinator import BrokerCoordinator

# Create coordinator
coordinator = BrokerCoordinator()

# Add 2 Upstox accounts (bypass 2000-instrument limit)
coordinator.add_broker(broker1, subscription_limit=2000, name="Account-1")
coordinator.add_broker(broker2, subscription_limit=2000, name="Account-2")

# Subscribe to 3000 instruments (auto-distributed!)
all_tokens = [...]  # 3000 tokens
distribution = coordinator.subscribe(all_tokens, mode="full")
print(f"Distribution: {distribution}")
# Output: {'Account-1': 2000, 'Account-2': 1000}

# Single unified callback
coordinator.on_tick(lambda ticks: print(f"Received {len(ticks)} ticks"))
coordinator.connect_all()
```

### Hybrid: Streaming + Polling

```python
# Stream specific ATM strikes for low latency
coordinator.subscribe(atm_strikes, mode="full")

# Poll full option chain every 5 seconds
coordinator.add_option_chain_poller(
    broker=broker,
    symbol="NIFTY",
    expiry="2025-12-09",
    poll_interval_seconds=5
)

# Both feed into same callback!
coordinator.on_tick(process_data)
coordinator.connect_all()
```

## 📖 Examples

Check out [`examples/`](examples/) directory:

- **`verify_upstox.py`**: Basic Upstox streaming test
- **`multi_broker_streaming.py`**: 2 accounts, 3000 instruments
- **`hybrid_streaming_polling.py`**: Real-time + snapshots combo

Test your setup:
```bash
python3 examples/verify_upstox.py
```

## 📚 Documentation

- **[Multi-Broker Setup Guide](docs/multi_broker_setup.md)**: Production architectures, best practices
- **[Broker Testing Summary](docs/broker_testing.md)**: Verified features per broker

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                 BrokerCoordinator                   │
│  (Manages multiple brokers + pollers)               │
└────────────┬────────────────────────┬───────────────┘
             │                        │
    ┌────────▼────────┐      ┌────────▼────────┐
    │ Upstox Broker 1 │      │ Upstox Broker 2 │
    │  WebSocket      │      │  Option Poller  │
    └────────┬────────┘      └────────┬────────┘
             │                        │
             └────────┬───────────────┘
                      │
              ┌───────▼────────┐
              │  Tick Callback │
              └───────┬────────┘
                      │
      ┌───────────────┼───────────────┐
      │               │               │
┌─────▼─────┐  ┌──────▼──────┐  ┌────▼──────┐
│   Redis   │  │ ClickHouse  │  │    S3     │
│ (Real-time)│ │ (Analytics) │  │ (Archive) │
└───────────┘  └─────────────┘  └───────────┘
```

### Components

1. **Instrument Master**: Parses broker scrip masters (JSON/CSV) → unified `Instrument` model
2. **Broker Interface**: Abstract base class with `connect()`, `subscribe()`, `fetch_option_chain()`
3. **Normalization**: Broker-specific WebSocket messages → standardized `Tick` dataclass
4. **Storage Layer**:
   - `RedisStorage`: Real-time LTP, OI, Volume caching
   - `ClickHouseStorage`: Time-series tick data for backtesting
   - `S3Snapshotter`: Option chain snapshots with timestamps

## 🔒 Security & Public Release

✅ **No hardcoded credentials** - All tokens use environment variables  
✅ **Comprehensive .gitignore** - Excludes `.env`, tokens, secrets  
✅ **Example configs** - Safe placeholder values only

## 📊 Broker Status

| Broker | Streaming | Option Chain | Greeks | Notes |
|--------|-----------|--------------|--------|-------|
| **Upstox** | ✅ | ✅ | ✅ | Production ready. 2000 instrument limit. |
| **Dhan** | ⚠️ | ⚠️ | - | REST API works. WebSocket needs paid subscription. |
| **Fyers** | 🚧 | 🚧 | - | SDK integrated, testing in progress. |
| **Zerodha** | 🚧 | ❌ | - | Coming soon. |

## 🚧 Roadmap

- [ ] Zerodha Kite full integration
- [ ] Fyers WebSocket verification
- [ ] Paper trading simulator
- [ ] Pre-built Docker images
- [ ] Kubernetes deployment configs
- [ ] Strategy backtesting framework

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## ⚠️ Disclaimer

This software is for **educational and research purposes only**. Trading in derivatives involves substantial risk. The authors are not responsible for any financial losses incurred through use of this software. Always test thoroughly in a paper trading environment first.

## 📄 License

[MIT License](LICENSE) - Free to use, modify, and distribute.

## 🙏 Acknowledgments

- [ranjanrak/optionchainstream](https://github.com/ranjanrak/optionchainstream) - Original inspiration
- Broker API teams for excellent documentation

---

**Made with ❤️ for the Indian algo trading community**
