# Dhan Live Market Feed v2 → option chain (+ IV)

Library modules. Nothing here logs in to Dhan: pass the current access token through a
`token_provider` callable (Dhan allows one active token per account).

## Module map

| Module | What it does |
|---|---|
| `optionchain_stream/dhan/packets.py` | Binary decoder for v2 response packets (ticker 2, index 1, quote 4, OI 5, prev-close 6, market status 7, full 8 with 5-level depth, disconnect 50), `iter_packets` for frames holding several packets, `ltt_to_utc`, JSON subscribe messages (≤100 instruments each). Matches the dhanhq 2.3.0 layouts. |
| `optionchain_stream/dhan/feed.py` | `plan_connections` (≤5,000 instruments/connection, default ≤3 connections, groups kept on one socket), `DhanMarketFeed` (one asyncio task per connection, paced subscribe, reconnect with backoff + full re-subscribe, 805 "too many connections" wait, auth-error callback, stall watchdog, token scrubbed from all errors/events). |
| `optionchain_stream/dhan/universe.py` | `near_expiry_universe`: the CE+PE contracts of the N nearest live expiries per underlying, plus the index and nearest future, with the right segment and mode (NSE_FNO full, BSE_FNO quote + OI, index ticker). |
| `optionchain_stream/instrument_master/dhan_provider.py` | Detailed scrip-master parser: segment, CE/PE/FUT/INDEX, expiry date, strike, lot size, exchange; `nearest_expiries`. No Redis, no pandas. |
| `optionchain_stream/chain_state.py` | `ChainAssembler` (per-contract vendor-raw state; fields never received stay `None`), `MinuteSnapshotter` (snapshot at every minute close 09:16…15:30 IST; callback or `async for`). |
| `optionchain_stream/iv.py` | Black-76 IV on the forward (future, else put-call-parity forward); caller-supplied rate; no dividends; calendar minutes to 15:30 IST over 365 days; OTM side solved; failure = `None` + reason, never `0.0`. |
| `optionchain_stream/brokers/dhan_broker.py` | `DhanBroker` (Broker interface) on top of the above, plus REST `fetch_option_chain` via dhanhq 2.3.0. |

## Usage

See `examples/dhan_chain_stream.py`.

## Modes

| Segment | Mode | Why |
|---|---|---|
| NSE_FNO | Full (code 21): LTP, LTQ, LTT, ATP, volume, buy/sell qty, OI, OI high/low, OHLC, 5-level depth | |
| BSE_FNO | Quote (17); OI arrives as separate code-5 packets | Dhan sends nothing for BSE_FNO in Full mode |
| IDX_I | Ticker (15) | Index has only LTP/LTT |

## Not in scope

Greeks (left as they were), 20-level depth, any storage/export.
