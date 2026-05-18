# AGENTS.md — AI Agent Usage Guide

This document is written for AI agents (Claude, GPT, Gemini, etc.) that are helping developers work with this repository. It gives you an accurate mental model of the codebase so you can answer questions, write code, and debug issues without misreading the architecture.

---

## What This Repository Does

`optionchain-stream-india` is a Python library for streaming and polling option chain data from Indian stock market brokers (Upstox, Fyers, Dhan, Zerodha). It provides:

1. **WebSocket streaming** — real-time tick data (LTP, OI, Volume, Bid/Ask) for subscribed instruments
2. **REST polling** — complete option chain snapshots with Greeks (Delta, Theta, Gamma, Vega, IV)
3. **WIDE format** — normalised flat rows with CE and PE side-by-side per strike
4. **Multi-broker coordination** — distribute 4000+ instruments across multiple accounts
5. **Quality flags** — automated detection of stale, zero, or incomplete data
6. **Storage backends** — Redis, ClickHouse, S3/Parquet

---

## Repository Navigation

Start here when exploring unfamiliar code:

| File | What it is |
|------|------------|
| `optionchain_stream/broker_interface.py` | Abstract base class — the full contract every broker must satisfy |
| `optionchain_stream/models.py` | All dataclasses: `Instrument`, `Tick`, `OptionChainRow`, `CycleHealth` |
| `optionchain_stream/poller.py` | `OptionChainPoller` — main entry point for polling with WIDE output |
| `optionchain_stream/formatters/wide.py` | `to_wide_rows()` — converts raw broker chain dict to flat `OptionChainRow` list |
| `optionchain_stream/broker_coordinator.py` | `BrokerCoordinator` — multi-broker token distribution and unified callback |
| `optionchain_stream/brokers/fyers_broker.py` | Most complete broker implementation — read this first |
| `optionchain_stream/brokers/upstox_broker.py` | Production-ready streaming + polling (OAuth daily token) |
| `optionchain_stream/brokers/upstox_analytics_broker.py` | Read-only broker using Upstox Analytics Token (1-year, no OAuth flow) |
| `optionchain_stream/instrument_cache.py` | Redis + in-memory caching for instrument masters |
| `streamlit_demo.py` | Full working demo of both streaming and polling modes |
| `examples/` | Runnable scripts for each broker and pattern |

---

## Architecture

### Data Flow

```
Broker SDK (WebSocket or REST)
    │
    ▼ broker normalizes to common format
Tick  ──────────────────────────────────►  on_tick callback (streaming)
    or
raw chain dict
    │
    ▼ BrokerCoordinator.fetch_chain()
OptionChainPoller.poll_once()
    │
    ▼ formatters/wide.py  to_wide_rows()
list[OptionChainRow]  +  CycleHealth
    │
    ▼ caller writes to:
Redis | ClickHouse | S3
```

### Component Responsibilities

**`BrokerInterface` (abstract)**
- Defines the contract. All brokers must implement: `authenticate()`, `get_instrument_provider()`, `subscribe(tokens, mode)`, `on_tick(callback)`, `connect()`, `fetch_option_chain(symbol, expiry)`.

**`BrokerCoordinator`**
- Holds N broker instances. Distributes tokens round-robin up to each broker's `subscription_limit`.
- `subscribe(tokens)` → returns `{'Account-1': 2000, 'Account-2': 1000}` distribution dict.
- `on_tick(callback)` — unified callback across all brokers.
- `connect_all()` — starts all broker WebSocket connections in threads.
- `fetch_chain(symbol, expiry)` — delegates to first available broker with option chain support.

**`OptionChainPoller`**
- Wraps coordinator. Calls `poll_once()` which fetches all symbols × all active expiries.
- Uses `MarketCalendar.is_market_open()` to guard — call this before `poll_once()`.
- Returns `(list[OptionChainRow], CycleHealth)`. Does not write to any storage.
- Pipeline daemon is expected to call this from a thread-pool at `interval_sec` intervals.

**`to_wide_rows()` (formatters/wide.py)**
- Input: raw `chain_response` dict (broker format), `prev_snapshot` dict keyed by strike.
- Output: `list[OptionChainRow]` — one row per strike with all CE and PE fields.
- Sets `quality_flag` on each row: `0`=clean, `1`=zero_ltp, `2`=missing_greeks, `4`=stale.

---

## Data Models

### `OptionChainRow` — WIDE format

One row per strike. All numeric fields default to `0.0` / `0` if not provided by the broker.

```python
@dataclass
class OptionChainRow:
    timestamp:     int        # Unix epoch seconds
    underlying:    str        # "NIFTY", "BANKNIFTY"
    expiry:        str        # "2025-12-25"
    strike:        float      # 25000.0
    ce_symbol:     str        # broker symbol string for the call
    ce_ltp:        float
    ce_bid:        float
    ce_ask:        float
    ce_open:       float
    ce_high:       float
    ce_low:        float
    ce_prev_close: float
    ce_volume:     int
    ce_oi:         int
    ce_iv:         float      # implied volatility (annualised, e.g. 0.12 = 12%)
    ce_delta:      float
    ce_theta:      float
    ce_gamma:      float
    ce_vega:       float
    pe_symbol:     str
    pe_ltp:        float
    # ... same 14 fields for PE side ...
    lotsize:       int
    quality_flag:  int        # 0=clean 1=zero_ltp 2=missing_greeks 4=stale
```

### `CycleHealth`

Returned alongside rows from `poll_once()`. Use this for alerting and observability.

```python
@dataclass
class CycleHealth:
    ts:               int       # cycle start time (epoch)
    cycle_type:       str       # always "option_live"
    symbols_expected: int       # len(poller._symbols)
    symbols_received: int       # symbols that succeeded
    gaps:             int       # symbols that raised exceptions
    stale_warnings:   int       # rows with quality_flag == 4
    duration_ms:      int       # wall time for entire poll_once()
    error:            str|None  # first exception message, if any
```

### `Tick` — WebSocket streaming

```python
@dataclass
class Tick:
    token:      str       # broker instrument token
    timestamp:  datetime
    last_price: float
    volume:     int
    oi:         int
    change:     float
    bid_price:  float
    ask_price:  float
    bid_qty:    int
    ask_qty:    int
```

### `Instrument` — normalised instrument master

```python
@dataclass
class Instrument:
    exchange:        str       # "NSE", "MCX"
    token:           str       # broker-agnostic token
    symbol:          str       # e.g. "NIFTY23OCT19500CE"
    name:            str       # underlying name e.g. "NIFTY"
    expiry:          datetime
    strike:          float
    lot_size:        int
    instrument_type: str       # "CE", "PE", "FUT", "EQ"
    broker_token:    str       # broker-specific token string
    tick_size:       float
```

---

## Broker Status and Capabilities

| Broker | fetch_option_chain | WebSocket | Greeks natively | Notes |
|--------|-------------------|-----------|-----------------|-------|
| Fyers | Yes — native `optionchain()` API, 50 strikes/side | Partial | Yes | Most complete REST implementation |
| Upstox (OAuth) | Yes — REST endpoint | Yes | Yes | Daily token; supports streaming + trading |
| Upstox (Analytics) | Yes — REST `/v2/option/chain` | No | Yes | **1-year token, no OAuth flow; read-only** — see below |
| Dhan | Partial — built from quotes | Yes (needs paid) | No | REST quota-limited |
| Zerodha | Chain reconstruction from tick data | Yes | No | `zerodha_chain.py` handles reconstruction |

---

## Common Patterns

### Pattern 1: Poll once and process rows

```python
from optionchain_stream.poller import OptionChainPoller
from optionchain_stream.broker_coordinator import BrokerCoordinator
from optionchain_stream.brokers.fyers_broker import FyersBroker

broker = FyersBroker(client_id=..., access_token=...)
coordinator = BrokerCoordinator()
coordinator.add_broker(broker, subscription_limit=2000, name="fyers")

poller = OptionChainPoller(
    broker_coordinator=coordinator,
    symbols=["NIFTY", "BANKNIFTY"],
    market_calendar=MarketCalendar(),
)

if poller.is_market_open():
    rows, health = poller.poll_once()
    clean_rows = [r for r in rows if r.quality_flag == 0]
    print(f"{len(clean_rows)} clean rows out of {len(rows)}")
```

### Pattern 1b: Upstox Analytics Token (no OAuth, 1-year token)

The Analytics Token is the simplest Upstox auth path for data-only pipelines — no
daily OAuth login, no redirect URI, no client secret. Token is valid for 1 year.

**Generate:** Upstox Developer Apps → Analytics tab → Generate Token
(`https://account.upstox.com/developer/apps#analytics`)

**Limitations:** read-only (no orders/positions), no WebSocket streaming,
`open`/`high`/`low` fields on rows are 0 (not returned by the API endpoint).

```python
from optionchain_stream.broker_coordinator import BrokerCoordinator
from optionchain_stream.poller import OptionChainPoller

# Option A — via from_config (recommended for pipeline use)
coordinator = BrokerCoordinator.from_config({
    "broker": "upstox",
    "analytics_token": "eyJ...",   # long-lived token, no api_key/api_secret needed
})

# Option B — construct directly
from optionchain_stream.brokers.upstox_analytics_broker import UpstoxAnalyticsBroker
broker = UpstoxAnalyticsBroker(analytics_token="eyJ...")
coordinator = BrokerCoordinator()
coordinator.add_broker(broker, subscription_limit=0, name="upstox-analytics")

poller = OptionChainPoller(
    broker_coordinator=coordinator,
    symbols=["NIFTY", "BANKNIFTY"],
    market_calendar=calendar,
)
rows, health = poller.poll_once()
```

**vs. OAuth UpstoxBroker:**

| Feature | `UpstoxBroker` (OAuth) | `UpstoxAnalyticsBroker` |
|---------|------------------------|-------------------------|
| Token lifetime | Daily (login required) | 1 year |
| OAuth flow | Required | Not needed |
| WebSocket streaming | Yes | No |
| Option chain fetch | Yes | Yes |
| Greeks in response | Yes | Yes |
| open/high/low fields | Yes | 0 (not in API) |
| Trading APIs | Yes | No |

### Pattern 2: Periodic polling loop

```python
import time, threading

def poll_loop(poller, interval_sec, on_rows):
    while True:
        if poller.is_market_open():
            rows, health = poller.poll_once()
            on_rows(rows, health)
        time.sleep(interval_sec)

t = threading.Thread(target=poll_loop, args=(poller, 300, handle_rows), daemon=True)
t.start()
```

### Pattern 3: Stream + Poll hybrid

```python
# Real-time ticks for ATM strikes
coordinator.subscribe(atm_tokens, mode="full")
coordinator.on_tick(handle_tick)
threading.Thread(target=coordinator.connect_all, daemon=True).start()

# Full chain snapshot every 5 minutes
poll_loop(poller, 300, handle_rows)
```

### Pattern 4: Filter by quality flag

```python
rows, health = poller.poll_once()

clean      = [r for r in rows if r.quality_flag == 0]
zero_ltp   = [r for r in rows if r.quality_flag == 1]
no_greeks  = [r for r in rows if r.quality_flag == 2]
stale      = [r for r in rows if r.quality_flag == 4]

# Alert if more than 10% of rows are stale
if len(stale) / max(len(rows), 1) > 0.1:
    alert("High stale ratio", health)
```

### Pattern 5: Raw option chain (without WIDE formatter)

```python
# When you need the raw nested broker format
chain = broker.fetch_option_chain("NIFTY", "2025-12-25")

# Standard response structure across all brokers:
# {
#   'spot_price': 24500.0,
#   'pcr': 1.23,
#   'strikes': [
#     {
#       'strike_price': 24000,
#       'call_options': {
#         'symbol': '...', 'ltp': 310.5, 'bid': 310.0, 'ask': 311.0,
#         'oi': 123456, 'volume': 789012,
#         'option_greeks': {'iv': 0.12, 'delta': 0.6, 'theta': -8.2, 'gamma': 0.001, 'vega': 12.3}
#       },
#       'put_options': { ... same structure ... }
#     },
#     ...
#   ]
# }
```

### Pattern 6: Multi-account to bypass limits

```python
# Upstox caps at 2000 instruments per account
# Use two accounts to cover 4000 instruments
coordinator = BrokerCoordinator()
coordinator.add_broker(upstox1, subscription_limit=2000, name="upstox-1")
coordinator.add_broker(upstox2, subscription_limit=2000, name="upstox-2")

distribution = coordinator.subscribe(tokens_4000, mode="full")
# → {'upstox-1': 2000, 'upstox-2': 2000}
```

---

## Adding a New Broker

To add support for a new broker, implement three things:

### Step 1: Instrument Provider (`instrument_master/`)

```python
# optionchain_stream/instrument_master/mybroker_provider.py
from .instrument_provider import InstrumentProvider
from optionchain_stream.models import Instrument

class MyBrokerProvider(InstrumentProvider):
    def fetch_instruments(self) -> list[Instrument]:
        # Download CSV/JSON from broker, parse each row into Instrument
        ...

    def get_active_expiries(self, underlying: str) -> list[str]:
        # Return list of expiry strings like ["2025-12-25", "2026-01-30"]
        ...

    def get_lotsize(self, underlying: str) -> int:
        ...
```

### Step 2: Broker Implementation (`brokers/`)

```python
# optionchain_stream/brokers/mybroker_broker.py
from optionchain_stream.broker_interface import BrokerInterface
from optionchain_stream.models import Tick

class MyBrokerBroker(BrokerInterface):
    def authenticate(self):
        # Set up SDK client with credentials from env vars
        ...

    def get_instrument_provider(self):
        return MyBrokerProvider(self._client)

    def subscribe(self, tokens: list[str], mode: str = "full"):
        # Tell WebSocket client which tokens to subscribe to
        ...

    def on_tick(self, callback):
        self._tick_callback = callback

    def connect(self):
        # Start WebSocket. This must be a blocking call.
        # On each message, normalize to list[Tick] and call self._tick_callback(ticks)
        ...

    def fetch_option_chain(self, symbol: str, expiry: str) -> dict:
        # Call REST API, normalize to standard chain dict:
        # { 'spot_price': float, 'pcr': float, 'strikes': [ { 'strike_price', 'call_options', 'put_options' } ] }
        ...
```

### Step 3: Register

Add the broker to `optionchain_stream/__init__.py` exports if needed, and add an entry in `examples/verify_mybroker.py`.

### Normalizing the chain response

Every broker's `fetch_option_chain()` must return this structure. The WIDE formatter depends on it:

```python
{
    'spot_price': 24500.0,
    'pcr': 1.23,
    'strikes': [
        {
            'strike_price': 24000,            # float or int
            'call_options': {
                'symbol': 'NSE:NIFTY...',
                'ltp': 310.5,
                'bid': 310.0,
                'ask': 311.0,
                'open': 280.0,
                'high': 320.0,
                'low': 270.0,
                'prev_close': 300.0,
                'oi': 123456,
                'volume': 789012,
                'option_greeks': {             # omit key if unavailable
                    'iv': 0.12,
                    'delta': 0.6,
                    'theta': -8.2,
                    'gamma': 0.001,
                    'vega': 12.3,
                }
            },
            'put_options': { ... }             # same structure
        }
    ]
}
```

If a field is unavailable, omit it or set to `None`. `to_wide_rows()` handles missing values with `0.0` / `0` defaults and sets appropriate quality flags.

---

## Instrument Caching

The `InstrumentCache` wraps Redis with an in-memory `dict` fallback.

```python
from optionchain_stream.instrument_cache import InstrumentCache

cache = InstrumentCache()  # auto-connects Redis if REDIS_HOST is set

cache.set("upstox:instruments", instruments_list)  # TTL = 3600s
instruments = cache.get("upstox:instruments")       # None if expired

stats = cache.get_stats()
# { 'hits': 42, 'misses': 1, 'backend': 'redis' }
```

The instrument providers call this automatically — you rarely need to interact with it directly.

---

## Storage Backends

All storage is optional. The library never writes to storage itself — callers decide.

### Redis (`redis_storage.py`)

```python
from optionchain_stream.redis_storage import RedisStorage

store = RedisStorage(host="localhost", port=6379)
store.store_tick("NIFTY", "NSE:NIFTY25D0925900CE", tick_dict)
chain = store.get_option_chain("NIFTY")  # all ticks for symbol
```

### ClickHouse (`clickhouse_storage.py`)

```python
from optionchain_stream.clickhouse_storage import ClickHouseStorage

store = ClickHouseStorage(host="localhost", port=9000, database="optionchain")
store.insert_ticks("option_ticks", rows_as_dicts)
```

### S3 Parquet (`s3_snapshotter.py`)

```python
from optionchain_stream.s3_snapshotter import S3Snapshotter

snapper = S3Snapshotter(bucket="my-bucket", prefix="optionchain/")
snapper.snapshot(rows_or_dicts)   # uploads timestamped Parquet file
```

---

## Rate Limits

| Broker | WebSocket connections | Instruments per connection | REST quota |
|--------|----------------------|---------------------------|------------|
| Upstox (OAuth) | 1 per account | 2000 | 250 req/s |
| Upstox (Analytics Token) | None — polling only | N/A | 250 req/s |
| Fyers | 5 per account | — | varies |
| Dhan | — | 100 | 10 req/s |
| Zerodha | 1 per account | 3000 | varies |

Recommended polling interval: **300 seconds** (5 minutes) to stay well within REST limits. Minimum safe interval: 30 seconds.

---

## Error Handling Patterns

`poll_once()` never raises. It catches per-symbol exceptions, increments `health.gaps`, and continues. Check `health.error` for the first exception message.

```python
rows, health = poller.poll_once()
if health.gaps > 0:
    log.warning("poll gaps=%d first_error=%s", health.gaps, health.error)
if health.symbols_received == 0:
    log.error("Complete polling failure — no symbols succeeded")
```

For streaming, brokers handle reconnection internally. If `broker.connect()` exits, restart it:

```python
import time
while True:
    try:
        broker.connect()
    except Exception as e:
        log.error("broker disconnected: %s — reconnecting in 5s", e)
        time.sleep(5)
```

---

## Market Hours Guard

`MarketCalendar.is_market_open()` returns `True` Monday–Friday, 09:15–15:30 IST. Call this before polling.

```python
from optionchain_stream.market_calendar import MarketCalendar

cal = MarketCalendar()
if not cal.is_market_open():
    print("Market closed — skipping poll")
```

---

## Authentication Notes

All brokers use OAuth2 access tokens that **expire daily** (typically at 06:00 AM IST). You must:

1. Generate a new access token each trading day before market open
2. Store it in the environment variable (e.g. `FYERS_ACCESS_TOKEN`)
3. Restart the process or reload the env var

Fyers token generation requires browser login + `fyers-apiv3` auth flow. See `examples/verify_fyers.py` for the complete auth sequence.

---

## Testing

```bash
# verify individual brokers
python3 examples/verify_upstox.py
python3 examples/verify_fyers.py
python3 examples/verify_dhan.py

# run test suite
pytest tests/ -v
```

---

## What NOT To Do

- Do not call `to_wide_rows()` with a chain dict that skips the `'strikes'` key — it returns an empty list silently.
- Do not share a single `BrokerInterface` instance between threads — most broker SDKs are not thread-safe.
- Do not poll faster than every 30 seconds — you will hit broker rate limits and get blocked.
- Do not store access tokens in code — always use environment variables.
- Do not assume Greeks are always present — check `quality_flag != 2` before using `ce_iv`, `ce_delta`, etc.

<!-- BEGIN BEADS INTEGRATION v:1 profile:full hash:d4f96305 -->
## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Git-friendly: Dolt-powered version control with native sync
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" --description="Detailed context" -t bug|feature|task -p 0-4 --json
bd create "Issue title" --description="What this issue is about" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**

```bash
bd update <id> --claim --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task atomically**: `bd update <id> --claim`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Auto-Sync

bd automatically syncs via Dolt:

- Each write auto-commits to Dolt history
- Use `bd dolt push`/`bd dolt pull` for remote sync
- No manual export/import needed!

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

For more details, see README.md and docs/QUICKSTART.md.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

<!-- END BEADS INTEGRATION -->
