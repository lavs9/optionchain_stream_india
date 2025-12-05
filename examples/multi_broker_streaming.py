"""
Multi-Broker Streaming Example

Demonstrates using 2 Upstox accounts to bypass the 2000-instrument limit.
Subscribes to 3000 instruments across 2 brokers with unified callback.
"""

import os
import sys
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.broker_coordinator import BrokerCoordinator
from optionchain_stream.brokers.upstox_broker import UpstoxBroker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # Get credentials from environment
    token1 = os.getenv("UPSTOX_ACCESS_TOKEN_1")
    token2 = os.getenv("UPSTOX_ACCESS_TOKEN_2")
    
    if not token1 or not token2:
        print("Please set UPSTOX_ACCESS_TOKEN_1 and UPSTOX_ACCESS_TOKEN_2")
        return
    
    # Create coordinator
    coordinator = BrokerCoordinator()
    
    # Add broker 1
    broker1 = UpstoxBroker(
        client_id=os.getenv("UPSTOX_CLIENT_ID_1", "id1"),
        client_secret=os.getenv("UPSTOX_CLIENT_SECRET_1", "secret1"),
        redirect_uri="http://localhost",
        access_token=token1
    )
    coordinator.add_broker(broker1, subscription_limit=2000, name="Upstox-Account1")
    
    # Add broker 2
    broker2 = UpstoxBroker(
        client_id=os.getenv("UPSTOX_CLIENT_ID_2", "id2"),
        client_secret=os.getenv("UPSTOX_CLIENT_SECRET_2", "secret2"),
        redirect_uri="http://localhost",
        access_token=token2
    )
    coordinator.add_broker(broker2, subscription_limit=2000, name="Upstox-Account2")
    
    # Get instruments from provider (using first broker)
    logging.info("Fetching instrument list...")
    provider = broker1.get_instrument_provider()
    all_instruments = provider.fetch_instruments()
    
    # Get NIFTY options (let's assume we want 3000 of them)
    nifty_options = [
        inst for inst in all_instruments
        if "NIFTY" in inst.symbol and inst.instrument_type in ["CE", "PE"]
    ][:3000]  # Take first 3000
    
    tokens = [inst.token for inst in nifty_options]
    
    logging.info(f"Found {len(tokens)} NIFTY option tokens")
    
    # Subscribe (auto-distributes across both brokers)
    distribution = coordinator.subscribe(tokens, mode="full")
    
    logging.info(f"Distribution: {distribution}")
    logging.info(f"Account 1: {distribution.get('Upstox-Account1', 0)} instruments")
    logging.info(f"Account 2: {distribution.get('Upstox-Account2', 0)} instruments")
    
    # Unified callback for all brokers
    tick_count = {'count': 0}
    
    def handle_ticks(ticks):
        tick_count['count'] += len(ticks)
        
        # Log first few ticks
        if tick_count['count'] <= 10:
            for tick in ticks:
                logging.info(f"Tick: {tick.token} @ {tick.last_price}")
        
        # Log stats every 100 ticks
        if tick_count['count'] % 100 == 0:
            logging.info(f"Total ticks received: {tick_count['count']}")
    
    coordinator.on_tick(handle_ticks)
    
    # Connect all brokers
    logging.info("Connecting brokers...")
    coordinator.connect_all()
    
    # Monitor
    import time
    try:
        while True:
            time.sleep(30)  # Every 30 seconds
            stats = coordinator.get_stats()
            logging.info(f"=== Stats ===")
            logging.info(f"Total ticks: {stats['total_ticks']}")
            logging.info(f"Uptime: {stats['uptime_seconds']:.0f}s")
            
            for broker_stat in stats['brokers']:
                logging.info(
                    f"  {broker_stat['name']}: "
                    f"Connected={broker_stat['connected']}, "
                    f"Subscriptions={broker_stat['subscriptions']}/{broker_stat['limit']}"
                )
    
    except KeyboardInterrupt:
        logging.info("Stopping...")
        coordinator.stop_all()

if __name__ == "__main__":
    main()
