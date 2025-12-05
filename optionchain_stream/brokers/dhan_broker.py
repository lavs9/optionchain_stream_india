import logging
from typing import List, Dict, Any, Callable
from datetime import datetime
from dhanhq import dhanhq, DhanFeed
from optionchain_stream.broker_interface import Broker
from optionchain_stream.models import Tick
from optionchain_stream.instrument_master.dhan_provider import DhanInstrumentProvider
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider

class DhanBroker(Broker):
    def __init__(self, client_id: str, access_token: str):
        self.client_id = client_id
        self.access_token = access_token
        self.instrument_provider = DhanInstrumentProvider()
        
        self.dhan = dhanhq(client_id, access_token)
        
        # DhanFeed for WebSocket (v2.0)
        self.feed = None
        self.callbacks = []
        self.subscribed_instruments = []  # List of (exchange_code: int, security_id: str)

    def authenticate(self):
        # Dhan auth is implicit in client init for SDK
        pass

    def get_instrument_provider(self) -> InstrumentProvider:
        return self.instrument_provider

    def subscribe(self, tokens: List[str], mode: str = "full"):
        """
        Subscribe to market data for given tokens.
        
        Args:
            tokens: List of security IDs (tokens)
            mode: Subscription mode (not actively used in DhanFeed v2.0)
        """
        instruments = []
        for token in tokens:
            inst = self.instrument_provider.get_instrument_by_token(token)
            if inst:
                # Map exchange to Dhan exchange code (int)
                exch_code = 0
                if inst.exchange in ['NSE', 'NSE_EQ']:
                    exch_code = 0  # NSE
                elif inst.exchange == 'NSE_FO':
                    exch_code = 1  # NSE_FNO
                elif inst.exchange in ['BSE', 'BSE_EQ']:
                    exch_code = 3  # BSE
                elif inst.exchange == 'BSE_FO':
                    exch_code = 4  # BSE_FNO
                elif inst.exchange == 'MCX':
                    exch_code = 5  # MCX
                
                # DhanFeed expects (exchange_code: int, security_id: str)
                instruments.append((exch_code, str(inst.token)))
        
        if instruments:
            self.subscribed_instruments.extend(instruments)

    def on_tick(self, callback: Callable[[List[Tick]], None]):
        self.callbacks.append(callback)

    def connect(self):
        """Connect to Dhan WebSocket using DhanFeed v2.0"""
        print("Connecting to Dhan WebSocket (v2.0)...")
        
        # DhanFeed expects instruments as list of (exchange_code: int, security_id: str)
        self.feed = DhanFeed(self.client_id, self.access_token, self.subscribed_instruments)
        self.feed.on_ticker = self._on_ticker
        self.feed.run_forever()

    def _on_ticker(self, data):
        # Normalize data
        # Dhan data structure needs to be mapped
        normalized_tick = self._normalize_tick(data)
        for callback in self.callbacks:
            callback([normalized_tick])

    def _normalize_tick(self, data: Dict) -> Tick:
        # Map Dhan data to Tick
        # Example data: {'type': 'Ticker', 'exchange_segment': 2, 'security_id': 456, 'LTP': 100.0, ...}
        
        return Tick(
            token=str(data.get('security_id', '0')),
            timestamp=datetime.now(), # Dhan might provide 'ltt'
            last_price=float(data.get('LTP', 0.0)),
            volume=int(data.get('volume', 0)),
            oi=int(data.get('OI', 0)),
            change=0.0, # Calculate
            bid_price=float(data.get('depth', {}).get('buy', [{}])[0].get('price', 0.0)) if 'depth' in data else 0.0,
            ask_price=float(data.get('depth', {}).get('sell', [{}])[0].get('price', 0.0)) if 'depth' in data else 0.0,
            bid_qty=int(data.get('depth', {}).get('buy', [{}])[0].get('quantity', 0)) if 'depth' in data else 0,
            ask_qty=int(data.get('depth', {}).get('sell', [{}])[0].get('quantity', 0)) if 'depth' in data else 0
        )

    def fetch_option_chain(self, symbol: str, expiry: str) -> Dict[str, Any]:
        """
        Fetch option chain using Dhan API.
        
        Args:
            symbol: Underlying symbol (e.g., 'NIFTY', 'BANKNIFTY')
            expiry: Expiry date in YYYY-MM-DD format.
        """
        try:
            # Dhan option_chain API requires (under_security_id, under_exchange_segment, expiry)
            
            # Simple mapping for common indices
            # Based on Dhan documentation, NIFTY is 13, BANKNIFTY is 25
            under_security_id = None
            under_exchange_segment = "IDX_I"  # Index segment
            
            if symbol == 'NIFTY': 
                under_security_id = "13"  # Nifty 50 Index
            elif symbol == 'BANKNIFTY':
                under_security_id = "25"  # Bank Nifty Index
            
            # If not found, try to find in provider
            if not under_security_id:
                inst = self.instrument_provider.get_instrument_by_symbol(symbol)
                if inst:
                    under_security_id = inst.token
                    # Determine segment from exchange
                    if 'INDEX' in inst.exchange:
                        under_exchange_segment = "IDX_I"
            
            if under_security_id:
                response = self.dhan.option_chain(
                    under_security_id=under_security_id,
                    under_exchange_segment=under_exchange_segment,
                    expiry=expiry
                )
                return response
            else:
                logging.warning(f"Could not find security_id for {symbol}")
                return {}
                
        except Exception as e:
            logging.error(f"Error fetching Dhan option chain: {e}")
            import traceback
            traceback.print_exc()
            return {}
