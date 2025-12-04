import logging
from typing import List, Dict, Any, Callable
from datetime import datetime
from dhanhq import dhanhq
from dhanhq import DhanFeed
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
        self.feed = None
        self.callbacks = []
        self.subscribed_tokens = []

    def authenticate(self):
        # Dhan auth is implicit in client init for SDK
        pass

    def get_instrument_provider(self) -> InstrumentProvider:
        return self.instrument_provider

    def subscribe(self, tokens: List[str], mode: str = "full"):
        # Dhan requires (exchange_segment, security_id) tuples for subscription
        # We need to look up the instrument to get the exchange segment
        
        instruments = []
        for token in tokens:
            inst = self.instrument_provider.get_instrument_by_token(token)
            if inst:
                # Map exchange to Dhan segment code
                # NSE_FO -> 2, NSE_EQ -> 1, etc. (Need to verify codes)
                # Assuming standard codes or using SDK constants if available
                # For now, let's assume we can derive it or use a mapping
                
                # Mapping (approximate, need verification):
                # NSE_EQ: 1, NSE_FNO: 2, BSE_EQ: 3, BSE_FNO: 4, MCX: 5
                
                exch_code = 0
                if inst.exchange == 'NSE' or inst.exchange == 'NSE_EQ': exch_code = 1
                elif inst.exchange == 'NSE_FO' or inst.exchange == 'NFO': exch_code = 2
                elif inst.exchange == 'BSE': exch_code = 3
                elif inst.exchange == 'BSE_FO': exch_code = 4
                elif inst.exchange == 'MCX' or inst.exchange == 'MCX_FO': exch_code = 5
                
                if exch_code > 0:
                    instruments.append((exch_code, inst.token))
        
        if instruments:
            self.subscribed_tokens.extend(instruments)
            if self.feed:
                self.feed.subscribe_instruments(instruments)

    def on_tick(self, callback: Callable[[List[Tick]], None]):
        self.callbacks.append(callback)

    def connect(self):
        print("Connecting to Dhan WebSocket...")
        self.feed = DhanFeed(self.client_id, self.access_token, instruments=self.subscribed_tokens)
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
        """
        # Need to map symbol/expiry to what Dhan expects.
        # Dhan option_chain API likely takes (exchange_segment, security_id, expiry)
        # We need to find the underlying security_id first.
        
        # This is complex because we need the underlying token.
        # For now, let's assume the user passes the underlying token as symbol or we look it up.
        
        # Placeholder implementation
        return {}
