# Option Chain Stream India

**Enhanced Real-Time Option Chain Streaming for Indian Markets**

This project is a robust, multi-broker solution for streaming, normalizing, and storing option chain data from major Indian stock brokers. It unifies data from **Zerodha**, **Upstox**, **Dhan**, and **Fyers** into a single, standardized format, enabling high-performance algorithmic trading and analytics.

> **Credits**: This project is an enhanced fork/clone of [optionchainstream](https://github.com/ranjanrak/optionchainstream) by [ranjanrak](https://github.com/ranjanrak). We gratefully acknowledge the original idea and codebase.

## Key Features

*   **Multi-Broker Support**: Seamless integration with:
    *   **Zerodha Kite** (WebSocket)
    *   **Upstox** (API v3 WebSocket & Option Chain)
    *   **Dhan** (HQ API WebSocket & Option Chain)
    *   **Fyers** (API v3 WebSocket)
*   **Unified Data Model**: All broker data is normalized into standard `Instrument` and `Tick` objects, abstracting away broker-specific nuances.
*   **Advanced Storage Architecture**:
    *   **Redis**: Real-time state management (LTP, OI, Volume).
    *   **ClickHouse**: High-speed time-series storage for historical tick data.
    *   **S3**: Archival of option chain snapshots.
*   **Option Chain Polling**: Fetch full option chain snapshots (including Greeks) on demand from supported brokers.
*   **Resilient**: Automatic reconnection and error handling for WebSocket streams.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/lavs9/optionchain_stream_india.git
    cd optionchain_stream_india
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

Set the following environment variables based on the broker you intend to use. You can use a `.env` file or export them directly.

### Zerodha
```bash
export KITE_API_KEY="your_api_key"
export KITE_ACCESS_TOKEN="your_access_token"
```

### Upstox
```bash
export UPSTOX_CLIENT_ID="your_client_id"
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
```

## Usage

### Streaming Data
You can use the unified `Broker` interface to stream data from any provider.

```python
from optionchain_stream.brokers.upstox_broker import UpstoxBroker
from optionchain_stream.brokers.dhan_broker import DhanBroker
import os

# Initialize Broker
broker = UpstoxBroker(
    client_id=os.getenv("UPSTOX_CLIENT_ID"),
    access_token=os.getenv("UPSTOX_ACCESS_TOKEN")
)

# Define Callback
def on_tick(ticks):
    for tick in ticks:
        print(f"Token: {tick.token}, LTP: {tick.last_price}, OI: {tick.oi}")

# Connect and Subscribe
broker.on_tick(on_tick)
broker.connect()

# Fetch instruments to find tokens
provider = broker.get_instrument_provider()
instruments = provider.fetch_instruments('NSE_FO')
nifty_tokens = [i.token for i in instruments if 'NIFTY' in i.symbol][:5]

broker.subscribe(nifty_tokens)
```

### Verification Scripts
We have provided verification scripts to test each broker independently:

*   **Zerodha**: `python3 verify_zerodha.py`
*   **Upstox**: `python3 verify_upstox.py`
*   **Dhan**: `python3 verify_dhan.py`
*   **Fyers**: `python3 verify_fyers.py`

## Architecture

1.  **Instrument Master**: Fetches and parses "Scrip Master" files (CSV/JSON) from brokers to map symbols to tokens.
2.  **Broker Interface**: A common `Broker` abstract base class defines methods like `connect`, `subscribe`, and `fetch_option_chain`.
3.  **Normalization Layer**: Converts broker-specific WebSocket messages into a standard `Tick` dataclass.
4.  **Storage Layer**:
    *   `RedisStorage`: Updates a Redis hash for each token with the latest tick.
    *   `ClickHouseStorage`: Batches ticks and inserts them into a ClickHouse table.

## License
[MIT License](LICENSE)
