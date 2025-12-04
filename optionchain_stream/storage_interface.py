from abc import ABC, abstractmethod
from typing import Dict, Any, List
from optionchain_stream.models import Tick

class Storage(ABC):
    """
    Abstract base class for data storage.
    """

    @abstractmethod
    def store_tick(self, symbol: str, token: int, data: Tick):
        """
        Store a single tick update.
        """
        pass

    @abstractmethod
    def get_option_chain(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Retrieve the current option chain for a symbol.
        """
        pass
    
    @abstractmethod
    def store_instruments(self, symbol: str, data: Any):
        """
        Store instrument master data.
        """
        pass
    
    @abstractmethod
    def get_instrument(self, token: int) -> Dict[str, Any]:
        """
        Get instrument details by token.
        """
        pass
