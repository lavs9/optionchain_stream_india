from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable
from optionchain_stream.models import Tick
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider

class Broker(ABC):
    """
    Abstract base class for stock brokers.
    """

    @abstractmethod
    def authenticate(self):
        """
        Authenticate with the broker API.
        """
        pass

    @abstractmethod
    def get_instrument_provider(self) -> InstrumentProvider:
        """
        Get the instrument provider for this broker.
        """
        pass

    @abstractmethod
    def subscribe(self, tokens: List[int], mode: str = "full"):
        """
        Subscribe to real-time updates for the given tokens.
        """
        pass
    
    @abstractmethod
    def on_tick(self, callback: Callable[[List[Tick]], None]):
        """
        Register a callback for tick data.
        The callback receives a list of standardized Tick objects.
        """
        pass

    @abstractmethod
    def connect(self):
        """
        Connect to the websocket stream.
        """
        pass

    @abstractmethod
    def fetch_option_chain(self, symbol: str, expiry: str) -> Dict[str, Any]:
        """
        Fetch full option chain snapshot (including Greeks if available).
        """
        pass
