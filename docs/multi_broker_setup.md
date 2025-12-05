# Multi-Broker Setup Guide

This guide shows how to use `BrokerCoordinator` to manage multiple broker instances and combine streaming with polling.

## Table of Contents

1. [Bypass Subscription Limits](#bypass-subscription-limits)
2. [Multi-Broker Hybrid](#multi-broker-hybrid)
3. [Streaming + Polling Hybrid](#streaming--polling-hybrid)
4. [Production Architecture](#production-architecture)

---

## Bypass Subscription Limits

**Use Case**: Subscribe to 3000 instruments when each Upstox account has a 2000-instrument limit.

**Setup**: 2 Upstox accounts

```python
from optionchain_stream.broker_coordinator import BrokerCoordinator
from optionchain_stream.brokers.upstox_broker import UpstoxBroker

# Create coordinator
coordinator = BrokerCoordinator()

# Add 2 broker instances (different accounts)
upstox1 = UpstoxBroker(
    client_id="account1_id",
    client_secret="secret1",
    redirect_uri="http://localhost",
    access_token="token1"
)
upstox2 = UpstoxBroker(
    client_id="account2_id",
    client_secret="secret2",
    redirect_uri="http://localhost",
    access_token="token2"
)

coordinator.add_broker(upstox1, subscription_limit=2000, name="Upstox-Account1")
coordinator.add_broker(upstox2, subscription_limit=2000, name="Upstox-Account2")

# Subscribe to 3000 instruments (auto-distributed: 2000 + 1000)
all_tokens =  ["token1", "token2", ...]  # 3000 tokens
distribution = coordinator.subscribe(all_tokens, mode="full")

print(f"Distribution: {distribution}")
# Output: {'Upstox-Account1': 2000, 'Upstox-Account2': 1000}

# Single unified callback for ALL ticks
def handle_all_ticks(ticks):
    for tick in ticks:
        print(f"Received: {tick.token} @ {tick.last_price}")

coordinator.on_tick(handle_all_ticks)

# Connect all brokers
coordinator.connect_all()
```

**Benefits**:
- ✅ Subscribe to 4000 instruments (2 × 2000)
- ✅ Single callback handles all data
- ✅ Automatic distribution

---

## Multi-Broker Hybrid

**Use Case**: Use Upstox for NIFTY instruments, Dhan for BANKNIFTY (diversify risk).

**Setup**: 1 Upstox + 1 Dhan account

```python
from optionchain_stream.broker_coordinator import BrokerCoordinator
from optionchain_stream.brokers.upstox_broker import UpstoxBroker
from optionchain_stream.brokers.dhan_broker import DhanBroker

coordinator = BrokerCoordinator()

# Upstox for NIFTY
upstox = UpstoxBroker(...)
coordinator.add_broker(upstox, subscription_limit=2000, name="Upstox-NIFTY")

# Dhan for BANKNIFTY  
dhan = DhanBroker(...)
coordinator.add_broker(dhan, subscription_limit=1500, name="Dhan-BANKNIFTY")

# Subscribe to different instruments per broker
nifty_tokens = [...]  # 1500 NIFTY options
banknifty_tokens = [...]  # 1000 BANKNIFTY options

# Auto-distributes: first 2000 to Upstox, next 1000 to Dhan
coordinator.subscribe(nifty_tokens + banknifty_tokens, mode="full")

coordinator.on_tick(handle_all_ticks)
coordinator.connect_all()
```

**Benefits**:
- ✅ Broker redundancy
- ✅ Diversified risk
- ✅ Mix free/paid tiers

---

## Streaming + Polling Hybrid

**Use Case**: Real-time streaming for ATM strikes + full option chain snapshot every 5 seconds.

**Setup**: 1 Upstox account (streaming) + 1 Upstox account (polling)

```python
from optionchain_stream.broker_coordinator import BrokerCoordinator
from optionchain_stream.brokers.upstox_broker import UpstoxBroker

coordinator = BrokerCoordinator()

# Broker for real-time streaming
upstox_stream = UpstoxBroker(...)
coordinator.add_broker(upstox_stream, subscription_limit=50, name="Upstox-Stream")

# Subscribe to specific ATM strikes (low latency)
atm_strikes = ["NSE_FO|12345", "NSE_FO|12346"]  # 5 ATM strikes
coordinator.subscribe(atm_strikes, mode="full")

# Broker for polling (can be same or different account)
upstox_poll = UpstoxBroker(...)

# Add option chain poller (polls every 5 seconds)
coordinator.add_option_chain_poller(
    broker=upstox_poll,
    symbol="NIFTY",
    expiry="2025-12-09",
    poll_interval_seconds=5,
    name="NIFTY-OptionChain"
)

# Unified callback receives BOTH streaming ticks AND polled data
def handle_data(ticks):
    for tick in ticks:
        if tick.token in atm_strikes:
            print(f"REAL-TIME ATM: {tick.token} @ {tick.last_price}")
        else:
            print(f"POLLED: {tick.token} @ {tick.last_price}")

coordinator.on_tick(handle_data)
coordinator.connect_all()

# Optional: Check stats
import time
time.sleep(10)
stats = coordinator.get_stats()
print(f"Total ticks received: {stats['total_ticks']}")
print(f"Brokers: {stats['brokers']}")
print(f"Pollers: {stats['pollers']}")
```

**Benefits**:
- ✅ Ultra-low latency for critical strikes
- ✅ Full market view via polling
- ✅ Cost-effective (only stream what you need)

---

## Production Architecture

**Use Case**: Production system with 3000+ instruments, redundancy, and monitoring.

```python
from optionchain_stream.broker_coordinator import BrokerCoordinator
from optionchain_stream.brokers.upstox_broker import UpstoxBroker
from optionchain_stream.storage.redis_storage import RedisStorage
from optionchain_stream.storage.clickhouse_storage import ClickHouseStorage
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

# Create coordinator
coordinator = BrokerCoordinator()

# Add multiple brokers for redundancy
for i in range(2):
    broker = UpstoxBroker(
        access_token=f"token_{i+1}",
        ...
    )
    coordinator.add_broker(broker, subscription_limit=2000, name=f"Upstox-{i+1}")

# Add option chain poller for snapshots
poller_broker = UpstoxBroker(...)
coordinator.add_option_chain_poller(
    broker=poller_broker,
    symbol="NIFTY",
    expiry="2025-12-09",
    poll_interval_seconds=60,  # Every minute
    name="NIFTY-Snapshot"
)

# Setup storage
redis = RedisStorage(host="localhost", port=6379)
clickhouse = ClickHouseStorage(host="localhost", port=9000)

# Unified callback with storage
def store_ticks(ticks):
    try:
        # Store in Redis (real-time cache)
        redis.store_ticks(ticks)
        
        # Batch store in ClickHouse (analytics)
        clickhouse.store_ticks(ticks)
        
        logging.info(f"Stored {len(ticks)} ticks")
    except Exception as e:
        logging.error(f"Storage error: {e}")

coordinator.on_tick(store_ticks)

# Subscribe to instruments
all_instruments = [...]  # 3000+ tokens
coordinator.subscribe(all_instruments, mode="full")

# Connect and start
coordinator.connect_all()

# Monitor health
import time
while True:
    time.sleep(60)  # Every minute
    stats = coordinator.get_stats()
    logging.info(f"Health Check - Ticks: {stats['total_ticks']}, "
                 f"Uptime: {stats['uptime_seconds']}s")
    
    # Check broker health
    for broker_stat in stats['brokers']:
        if not broker_stat['connected']:
            logging.warning(f"Broker {broker_stat['name']} disconnected!")
```

**Features**:
- ✅ 4000+ instrument capacity
- ✅ Redundant connections
- ✅ Real-time + batch storage
- ✅ Health monitoring
- ✅ Production logging

---

## Best Practices

1. **Capacity Planning**: 
   - Keep 10-20% buffer per broker
   - Monitor `available_capacity()` via `get_stats()`

2. **Error Handling**:
   - Wrap callbacks in try-except
   - Log all errors

3. **Connection Management**:
   - Stagger broker connections (avoid simultaneous)
   - Monitor connection health

4. **Performance**:
   - Use Redis for real-time cache
   - Batch writes to ClickHouse (every 5-10 seconds)
   - Poll option chains at reasonable intervals (5-60s)

5. **Cost Optimization**:
   - Stream only high-priority instruments
   - Poll for full snapshots
   - Use free tier accounts strategically

## API Reference

### BrokerCoordinator

**`add_broker(broker, subscription_limit, name="")`**
- Registers a broker instance
- `subscription_limit`: Max instruments (e.g., 2000 for Upstox full mode)

**`subscribe(tokens, mode="full")`**
- Auto-distributes instruments across brokers
- Returns: Dict of {broker_name: count}

**`add_option_chain_poller(broker, symbol, expiry, poll_interval_seconds, name="")`**
- Adds periodic polling for option chains
- Returns: OptionChainPoller instance

**`on_tick(callback)`**
- Registers callback for all data (streams + polls)
- Callback signature: `(ticks: List[Tick]) -> None`

**`connect_all()`**
- Connects all brokers and starts all pollers

**`get_stats()`**
- Returns health metrics and statistics

**`stop_all()`**
- Stops all pollers (broker disconnection depends on implementation)
