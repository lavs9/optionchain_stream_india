import logging
from multiprocessing import Queue
from typing import List, Dict, Any
from optionchain_stream.broker_interface import Broker
from optionchain_stream.storage_interface import Storage
from optionchain_stream.redis_storage import RedisStorage
from optionchain_stream.models import Tick

class OptionChain:
    def __init__(self, symbol: str, expiry: str, broker: Broker, storage: Storage = None, underlying: bool = False):
        self.symbol = symbol
        self.expiry = expiry
        self.broker = broker
        self.storage = storage if storage else RedisStorage()
        self.underlying = underlying
        self.q = Queue()

    def sync_instruments(self):
        """
        Sync master instrument to storage.
        """
        provider = self.broker.get_instrument_provider()
        instruments = provider.fetch_instruments()
        # Logic to store instruments would go here
        pass

    def _process_ticks(self, ticks: List[Tick]):
        for tick in ticks:
            # Store to storage
            self.storage.store_tick(self.symbol, tick.token, tick)
            # Put to queue for consumption
            self.q.put(tick)

    def create_option_chain(self):
        """
        Start the stream.
        """
        # 1. Fetch tokens for the symbol and expiry
        # In a real scenario, we'd use the instrument provider to filter tokens
        tokens = [] 
        
        # 2. Subscribe
        self.broker.on_tick(self._process_ticks)
        self.broker.connect()
        self.broker.subscribe(tokens)

        # 3. Yield data
        while True:
            yield self.q.get()

class OptionChainPoller:
    def __init__(self, symbol: str, expiry: str, broker: Broker, interval: int = 60, storage: Storage = None):
        """
        Polls full option chain snapshot at regular intervals.
        
        Args:
            symbol: Underlying symbol (e.g., 'NIFTY')
            expiry: Expiry date (e.g., '2023-10-26')
            broker: Broker instance
            interval: Polling interval in seconds
            storage: Storage backend (e.g., ClickHouseStorage, S3Snapshotter)
        """
        self.symbol = symbol
        self.expiry = expiry
        self.broker = broker
        self.interval = interval
        self.storage = storage
        self.running = False

    def start(self):
        import time
        import threading
        
        self.running = True
        logging.info(f"Starting Option Chain Poller for {self.symbol} ({self.expiry}) every {self.interval}s")
        
        def poll_loop():
            while self.running:
                try:
                    start_time = time.time()
                    
                    # Fetch snapshot
                    snapshot = self.broker.fetch_option_chain(self.symbol, self.expiry)
                    
                    if snapshot:
                        # Store snapshot
                        if self.storage:
                            # If storage supports storing raw snapshots (like S3)
                            if hasattr(self.storage, 'snapshot'):
                                self.storage.snapshot(snapshot, prefix=f"option_chain/{self.symbol}/{self.expiry}")
                            else:
                                # If storage expects ticks, we might need to parse it.
                                # But usually polling is for full snapshots.
                                logging.info(f"Snapshot fetched for {self.symbol}. Storage does not support direct snapshot.")
                    
                    # Wait for next interval
                    elapsed = time.time() - start_time
                    sleep_time = max(0, self.interval - elapsed)
                    time.sleep(sleep_time)
                    
                except Exception as e:
                    logging.error(f"Error in polling loop: {e}")
                    time.sleep(5) # Retry delay

        self.thread = threading.Thread(target=poll_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2.0)
