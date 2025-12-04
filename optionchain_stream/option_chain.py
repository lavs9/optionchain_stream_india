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
