# Option Chain Stream India

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Enterprise-grade real-time option chain streaming for Indian markets with multi-broker support, unified data models, WIDE-format output with Greeks, and production-ready storage.

> Built on [optionchainstream](https://github.com/ranjanrak/optionchainstream) by [ranjanrak](https://github.com/ranjanrak). Extended with multi-broker coordination, option chain polling, WIDE formatter, Greeks, and quality flags.

---

## For AI Agents

If you are an AI assistant helping a developer with this repository, start with **[AGENTS.md](AGENTS.md)**. It covers architecture, data models, code patterns, broker implementation guides, and decision trees.

---

## Features

### Multi-Broker Support

| Broker | Streaming | Option Chain | Greeks | Status |
|--------|-----------|--------------|--------|--------|
| **Upstox** (OAuth) | Yes | Yes | Yes | Daily token; streaming + trading. 2000 instrument limit per account. |
| **Upstox** (Analytics Token) | No | Yes | Yes | **1-year token, no OAuth flow.** Read-only polling; no streaming. |
| **Fyers** | Partial | Yes | Yes | Native `optionchain()` API. 50 strikes per side. WebSocket in progress. |
| **Dhan** | Yes | Partial | No | REST API works. WebSocket needs paid subscription. |
| **Zerodha** | Yes | Partial | No | Chain reconstruction from tick data. |

### Core Capabilities

- **Real-time WebSocket Streaming** — sub-millisecond latency for equities, futures, and options
- **Option Chain Polling** — full snapshots with Greeks for NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY
- **WIDE Format Output** — CE and PE side-by-side in a single flat row per strike, with 30+ fields
- **Quality Flags** — automatic detection of zero LTP, missing Greeks, and stale data
- **Multi-Broker Coordinator** — distribute 4000+ instruments across multiple accounts
- **Market-Hours Poller** — `is_market_open()` guard; skips polling outside NSE hours
- **Production Storage** — Redis (real-time), ClickHouse (analytics), S3/Parquet (archival)
- **Instrument Caching** — Redis-backed with in-memory fallback, 1-hour TTL

---

## Installation

```bash
git clone https://github.com/lavs9/optionchain_stream_india.git
cd optionchain_stream_india

python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

# Zerodha extras (optional)
pip install -e ".[zerodha]"
```

---

## Configuration

All credentials are read from environment variables. Never commit `.env` files.

### Upstox — OAuth (daily token, streaming + trading)
```bash
export UPSTOX_CLIENT_ID="your_client_id"
export UPSTOX_CLIENT_SECRET="your_client_secret"
export UPSTOX_REDIRECT_URI="http://localhost"
export UPSTOX_ACCESS_TOKEN="your_access_token"   # expires daily
```

### Upstox — Analytics Token (1-year, no OAuth flow, read-only)
Generate once at https://account.upstox.com/developer/apps#analytics
```bash
export UPSTOX_ANALYTICS_TOKEN="eyJ..."   # valid for 1 year
```
Use `UpstoxAnalyticsBroker` or pass `analytics_token` to `BrokerCoordinator.from_config()`.
No `CLIENT_ID`, `CLIENT_SECRET`, or `REDIRECT_URI` needed.

### Fyers
```bash
export FYERS_CLIENT_ID="your_client_id"
export FYERS_ACCESS_TOKEN="your_access_token"   # expires daily, re-generate each morning
```

### Dhan
```bash
export DHAN_CLIENT_ID="your_client_id"
export DHAN_ACCESS_TOKEN="your_access_token"
```

### Zerodha
```bash
export ZERODHA_API_KEY="your_api_key"
export ZERODHA_ACCESS_TOKEN="your_access_token"
```

### Storage (optional)
```bash
# Redis — instrument cache + real-time storage
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export REDIS_DB="0"

# ClickHouse — time-series analytics
export CLICKHOUSE_HOST="localhost"
export CLICKHOUSE_PORT="9000"
export CLICKHOUSE_USER="default"
export CLICKHOUSE_DB="optionchain"

# S3 — Parquet archival
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
export S3_BUCKET_NAME="your_bucket"
```

---

## Quick Start

### 1. Poll Option Chain (WIDE format with Greeks)

```python
from optionchain_stream.brokers.fyers_broker import FyersBroker
from optionchain_stream.broker_coordinator import BrokerCoordinator
from optionchain_stream.poller import OptionChainPoller
from optionchain_stream.market_calendar import MarketCalendar  # market-hours guard

broker = FyersBroker(
    client_id=os.getenv("FYERS_CLIENT_ID"),
    access_token=os.getenv("FYERS_ACCESS_TOKEN"),
)

coordinator = BrokerCoordinator()
coordinator.add_broker(broker, subscription_limit=2000, name="fyers-1")

poller = OptionChainPoller(
    broker_coordinator=coordinator,
    symbols=["NIFTY", "BANKNIFTY"],
    market_calendar=MarketCalendar(),
    interval_sec=300,
)

if poller.is_market_open():
    rows, health = poller.poll_once()
    print(f"Got {len(rows)} rows | gaps={health.gaps} | {health.duration_ms}ms")
    for row in rows[:3]:
        print(f"  {row.underlying} {row.strike:>8.0f}  CE={row.ce_ltp}  PE={row.pe_ltp}  flag={row.quality_flag}")
```

### 2. Stream Real-Time Ticks (WebSocket)

```python
from optionchain_stream.brokers.upstox_broker import UpstoxBroker

broker = UpstoxBroker(
    client_id=os.getenv("UPSTOX_CLIENT_ID"),
    client_secret=os.getenv("UPSTOX_CLIENT_SECRET"),
    redirect_uri="http://localhost",
    access_token=os.getenv("UPSTOX_ACCESS_TOKEN"),
)

def on_tick(ticks):
    for tick in ticks:
        print(f"{tick.token}: ltp={tick.last_price}  oi={tick.oi}  vol={tick.volume}")

provider = broker.get_instrument_provider()
instruments = provider.fetch_instruments()
nifty_options = [i for i in instruments if "NIFTY" in i.symbol][:20]

broker.on_tick(on_tick)
broker.subscribe([i.token for i in nifty_options], mode="full")
broker.connect()  # blocking
```

### 2b. Poll Option Chain via Upstox Analytics Token (no daily login)

```python
from optionchain_stream.broker_coordinator import BrokerCoordinator
from optionchain_stream.poller import OptionChainPoller

coordinator = BrokerCoordinator.from_config({
    "broker": "upstox",
    "analytics_token": os.getenv("UPSTOX_ANALYTICS_TOKEN"),
})

poller = OptionChainPoller(
    broker_coordinator=coordinator,
    symbols=["NIFTY", "BANKNIFTY"],
    market_calendar=calendar,
)
rows, health = poller.poll_once()
```

Or construct the broker directly:
```python
from optionchain_stream.brokers.upstox_analytics_broker import UpstoxAnalyticsBroker

broker = UpstoxAnalyticsBroker(analytics_token=os.getenv("UPSTOX_ANALYTICS_TOKEN"))
chain = broker.fetch_option_chain("NIFTY", "2026-05-29")
```

### 3. Multi-Broker Coordinator (bypass per-account limits)

```python
from optionchain_stream.broker_coordinator import BrokerCoordinator

coordinator = BrokerCoordinator()
coordinator.add_broker(broker1, subscription_limit=2000, name="Account-1")
coordinator.add_broker(broker2, subscription_limit=2000, name="Account-2")

# 3000 tokens auto-distributed across both accounts
distribution = coordinator.subscribe(all_tokens, mode="full")
# → {'Account-1': 2000, 'Account-2': 1000}

coordinator.on_tick(lambda ticks: print(f"Received {len(ticks)} ticks"))
coordinator.connect_all()
```

### 4. Raw Option Chain Polling (without WIDE formatter)

```python
# Use directly when you need the nested broker response
chain = broker.fetch_option_chain("NIFTY", "2025-12-25")
print(f"Spot: {chain['spot_price']}  PCR: {chain['pcr']}")

for strike in chain['strikes'][:5]:
    ce = strike['call_options']
    pe = strike['put_options']
    print(f"Strike {strike['strike_price']}: CE={ce['ltp']} IV={ce['option_greeks']['iv']}  "
          f"PE={pe['ltp']} IV={pe['option_greeks']['iv']}")
```

### 5. Streamlit Demo

```bash
export FYERS_CLIENT_ID="..."
export FYERS_ACCESS_TOKEN="..."
streamlit run streamlit_demo.py
```

Features: multi-broker selector, real-time option chain table, IV smile chart, OI visualizations, auto-refresh.

---

## WIDE Format

`OptionChainPoller.poll_once()` returns `list[OptionChainRow]` — one row per strike with CE and PE fields side by side.

```
timestamp | underlying | expiry | strike | ce_symbol | ce_ltp | ce_bid | ce_ask |
ce_open | ce_high | ce_low | ce_prev_close | ce_volume | ce_oi |
ce_iv | ce_delta | ce_theta | ce_gamma | ce_vega |
pe_symbol | pe_ltp | ... (same 14 fields) | lotsize | quality_flag
```

### Quality Flags

| Flag | Meaning | Action |
|------|---------|--------|
| `0` | Clean | Safe to use |
| `1` | Zero LTP — stale price on either side | Skip or alert |
| `2` | Greeks missing or both IVs are zero | Skip Greeks fields |
| `4` | Stale — all price/Greek fields identical to previous cycle | Likely no quote update |

---

## Architecture

```
Broker (WebSocket / REST)
  └─ normalize ──► Tick / raw chain dict
                         │
             BrokerCoordinator
             (distributes tokens, unified callback)
                         │
              OptionChainPoller
              (market-hours guard, per-expiry fetch)
                         │
             WIDE Formatter (to_wide_rows)
             (flat OptionChainRow + quality_flag)
                         │
          ┌──────────────┼──────────────┐
       Redis          ClickHouse        S3
    (real-time)      (analytics)     (Parquet)
```

### Package Layout

```
optionchain_stream/
├── __init__.py               # exports OptionChainPoller, OptionChainRow, CycleHealth
├── models.py                 # Instrument, Tick, OptionChainRow, CycleHealth dataclasses
├── broker_interface.py       # Abstract base class — contract all brokers must satisfy
├── broker_coordinator.py     # Multi-broker orchestration and token distribution
├── poller.py                 # OptionChainPoller — market-hours guard + WIDE output
├── config.py                 # Environment variable loading
├── instrument_cache.py       # Redis + in-memory instrument caching
├── redis_storage.py          # Real-time tick persistence
├── clickhouse_storage.py     # Time-series analytics storage
├── s3_snapshotter.py         # Parquet archival to S3
├── storage_interface.py      # Abstract storage interface
├── brokers/
│   ├── fyers_broker.py       # Fyers — native option chain API, 50 strikes
│   ├── upstox_broker.py           # Upstox — WebSocket + REST, OAuth daily token
│   ├── upstox_analytics_broker.py # Upstox — REST-only, 1-year Analytics Token
│   ├── dhan_broker.py        # Dhan — REST + WebSocket
│   ├── zerodha_broker.py     # Zerodha — WebSocket streaming
│   └── zerodha_chain.py      # Zerodha chain reconstruction from tick data
├── instrument_master/
│   ├── instrument_provider.py  # Abstract base
│   ├── fyers_provider.py
│   ├── upstox_provider.py
│   ├── dhan_provider.py
│   └── zerodha_provider.py
└── formatters/
    └── wide.py               # to_wide_rows() — converts nested chain to flat WIDE rows
```

---

## Documentation

- **[AGENTS.md](AGENTS.md)** — AI agent and LLM usage guide (architecture, patterns, broker implementation guide)
- **[docs/API_USAGE.md](docs/API_USAGE.md)** — Polling vs Streaming decision guide
- **[docs/BROKER_APIS.md](docs/BROKER_APIS.md)** — Rate limits and official API links per broker
- **[docs/EXAMPLES.md](docs/EXAMPLES.md)** — 11 ready-to-run code examples
- **[docs/multi_broker_setup.md](docs/multi_broker_setup.md)** — Production architecture guide
- **[docs/streamlit_demo.md](docs/streamlit_demo.md)** — Streamlit deployment guide

---

## Examples

```bash
python3 examples/verify_upstox.py         # basic Upstox streaming test
python3 examples/verify_fyers.py          # Fyers option chain test
python3 examples/verify_dhan.py           # Dhan API test
python3 examples/multi_broker_streaming.py    # 2 accounts, 3000 instruments
python3 examples/hybrid_streaming_polling.py  # real-time + snapshot combo
```

---

## Roadmap

- [ ] Fyers WebSocket streaming (in progress)
- [ ] Zerodha full option chain via REST
- [ ] Greeks computation for brokers that don't provide them natively
- [ ] Paper trading simulator
- [ ] Docker images and Kubernetes configs
- [ ] Strategy backtesting framework

---

## Security

- No hardcoded credentials — all tokens via environment variables
- `.gitignore` covers `.env`, `*.token`, `*.key`, `credentials.json`, `secrets.toml`
- Never commit access tokens — they are daily-expiry secrets

---

## Disclaimer

For educational and research purposes only. Trading in derivatives involves substantial risk. The authors are not responsible for any financial losses. Always test thoroughly in a paper trading environment first.

---

## License

[MIT License](LICENSE)

## Credits

- [ranjanrak/optionchainstream](https://github.com/ranjanrak/optionchainstream) — original inspiration
