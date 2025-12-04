from abc import ABC, abstractmethod
from typing import List, Dict
from optionchain_stream.models import Instrument

class InstrumentProvider(ABC):
    @abstractmethod
    def fetch_instruments(self, exchange: str = 'NFO') -> List[Instrument]:
        """
        Fetch and parse instruments from the broker's master source.
        """
        pass
    
    @abstractmethod
    def get_instrument_by_token(self, token: int) -> Instrument:
        """
        Get instrument details by token.
        """
        pass
    
    @abstractmethod
    def get_instrument_by_symbol(self, symbol: str) -> Instrument:
        """
        Get instrument details by symbol.
        """
        pass
