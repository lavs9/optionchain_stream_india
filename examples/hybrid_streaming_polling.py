"""
Hybrid Streaming + Polling Example

Demonstrates combining:
1. Real-time streaming for specific ATM strikes (low latency)
2. Option chain polling every 5 seconds for full snapshot

This gives you the best of both worlds:
- Ultra-low latency for critical strikes
- Complete market view via periodic polling
"""

import os
import sys
import logging
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.broker_coordinator import BrokerCoordinator
from optionchain_stream.brokers.upstox_broker import UpstoxBroker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    token = os.getenv("UPSTOX_ACCESS_TOKEN")
    
    if not token:
        print("Please set UPSTOX_ACCESS_TOKEN")
        return
    
    # Create coordinator
    coordinator = BrokerCoordinator()
    
    # Broker for real-time streaming
    stream_broker = UpstoxBroker(
        client_id=os.getenv("UPSTOX_CLIENT_ID", "dummy"),
        client_secret=os.getenv("UPSTOX_CLIENT_SECRET", "dummy"),
        redirect_uri="http://localhost",
        access_token=token
    )
    coordinator.add_broker(stream_broker, subscription_limit=50, name="Upstox-Stream")
    
    # Get ATM strikes for NIFTY
    logging.info("Fetching NIFTY instruments...")
    provider = stream_broker.get_instrument_provider()
    instruments = provider.fetch_instruments()
    
    # Find current month NIFTY options (simplified - just take first 5)
    nifty_options = [
        inst for inst in instruments
        if "NIFTY" in inst.symbol and inst.instrument_type == "CE"
    ][:5]  # Take 5 call options as example
    
    atm_tokens = [inst.token for inst in nifty_options]
    
    logging.info(f"Subscribing to {len(atm_tokens)} ATM strikes for streaming")
    coordinator.subscribe(atm_tokens, mode="full")
    
    # Add option chain poller (using same broker, can be different)
    logging.info("Adding option chain poller (5-second interval)")
    
    # Find nearest expiry
    expiries = set()
    for inst in instruments:
        if "NIFTY" in inst.symbol and inst.instrument_type == "CE" and inst.expiry:
            expiries.add(inst.expiry.strftime("%Y-%m-%d"))
    
    nearest_expiry = sorted(expiries)[0] if expiries else "2025-12-09"
    
    coordinator.add_option_chain_poller(
        broker=stream_broker,  # Can use same or different broker
        symbol="NIFTY",
        expiry=nearest_expiry,
        poll_interval_seconds=5,
        name="NIFTY-OptionChain-Poller"
    )
    
    # Unified callback handles BOTH streaming and polled data
    stats = {'stream_ticks': 0, 'poll_ticks': 0, 'total': 0}
    
    def handle_data(ticks):
        stats['total'] += len(ticks)
        
        for tick in ticks:
            if tick.token in atm_tokens:
                stats['stream_ticks'] += 1
                # This is real-time streaming data (< 1ms latency)
                logging.info(f"STREAM: {tick.token} @ {tick.last_price} (Real-time)")
            else:
                stats['poll_ticks'] += 1
                # This is polled data (5-second intervals)
                logging.debug(f"POLL: {tick.token} @ {tick.last_price} (Snapshot)")
        
        # Log stats every 20 ticks
        if stats['total'] % 20 == 0:
            logging.info(
                f"Stats - Stream: {stats['stream_ticks']}, "
                f"Poll: {stats['poll_ticks']}, "
                f"Total: {stats['total']}"
            )
    
    coordinator.on_tick(handle_data)
    
    # Connect and start
    logging.info("Starting hybrid streaming + polling...")
    coordinator.connect_all()
    
    # Monitor
    try:
        while True:
            time.sleep(30)
            coord_stats = coordinator.get_stats()
            logging.info(f"=== Coordinator Stats ===")
            logging.info(f"Total ticks: {coord_stats['total_ticks']}")
            logging.info(f"Brokers: {len(coord_stats['brokers'])} connected")
            logging.info(f"Pollers: {len(coord_stats['pollers'])} running")
            
            for poller_stat in coord_stats['pollers']:
                logging.info(
                    f"  Poller {poller_stat['symbol']}: "
                    f"Running={poller_stat['running']}, "
                    f"Interval={poller_stat['interval']}s"
                )
    
    except KeyboardInterrupt:
        logging.info("Stopping...")
        coordinator.stop_all()

if __name__ == "__main__":
    main()
