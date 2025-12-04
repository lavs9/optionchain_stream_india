import time
from typing import List, Dict, Any, Callable
from datetime import datetime
from optionchain_stream.broker_interface import Broker
from optionchain_stream.storage_interface import Storage
from optionchain_stream.option_chain import OptionChain
from optionchain_stream.models import Tick, Instrument
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider

class MockInstrumentProvider(InstrumentProvider):
    def fetch_instruments(self, exchange: str = 'NFO') -> List[Instrument]:
        return [
            Instrument("NFO", 123, "NIFTY23OCT19500CE", "NIFTY", datetime.now(), 19500, 50, "CE", "123", 0.05)
        ]
    def get_instrument_by_token(self, token: int) -> Instrument:
        return Instrument("NFO", 123, "NIFTY23OCT19500CE", "NIFTY", datetime.now(), 19500, 50, "CE", "123", 0.05)
    def get_instrument_by_symbol(self, symbol: str) -> Instrument:
        return Instrument("NFO", 123, "NIFTY23OCT19500CE", "NIFTY", datetime.now(), 19500, 50, "CE", "123", 0.05)

class MockBroker(Broker):
    def __init__(self):
        self.callback = None
        self.provider = MockInstrumentProvider()

    def authenticate(self):
        print("MockBroker authenticated")

    def get_instrument_provider(self) -> InstrumentProvider:
        return self.provider

    def subscribe(self, tokens: List[int], mode: str = "full"):
        print(f"Subscribed to {tokens}")
        # Simulate ticks
        for i in range(5):
            time.sleep(0.5)
            if self.callback:
                tick = Tick(
                    token=123,
                    timestamp=datetime.now(),
                    last_price=100.0 + i,
                    volume=1000 + i*10,
                    oi=5000 + i*50,
                    change=0.5
                )
                self.callback([tick])

    def on_tick(self, callback: Callable[[List[Tick]], None]):
        self.callback = callback

    def connect(self):
        print("MockBroker connected")

class MockStorage(Storage):
    def store_tick(self, symbol: str, token: int, data: Tick):
        print(f"Stored tick for {symbol}: {data}")

    def get_option_chain(self, symbol: str) -> List[Dict[str, Any]]:
        return []

    def store_instruments(self, symbol: str, data: Any):
        pass

    def get_instrument(self, token: int) -> Dict[str, Any]:
        return {}

def test_stream():
    broker = MockBroker()
    storage = MockStorage()
    # Note: OptionChain class might need update to handle new Tick model internally if it does processing
    # For now assuming it just passes through
    oc = OptionChain("NIFTY", "2023-10-26", broker, storage)
    
    print("Starting stream...")
    broker.on_tick(oc._process_ticks)
    broker.connect()
    broker.subscribe([123])

if __name__ == "__main__":
    test_stream()
