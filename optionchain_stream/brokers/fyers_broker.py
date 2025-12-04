import logging
from typing import List, Dict, Any, Callable
from datetime import datetime
from fyers_apiv3.FyersWebsocket import data_ws
from optionchain_stream.broker_interface import Broker
from optionchain_stream.models import Tick
from optionchain_stream.instrument_master.fyers_provider import FyersInstrumentProvider
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider

class FyersBroker(Broker):
    def __init__(self, client_id: str, access_token: str):
        self.client_id = client_id
        self.access_token = access_token
        self.instrument_provider = FyersInstrumentProvider()
        self.ws = None
        self.callbacks = []
        self.subscribed_tokens = []

    def authenticate(self):
        # Fyers auth is implicit via access_token passed to socket
        pass

    def get_instrument_provider(self) -> InstrumentProvider:
        return self.instrument_provider

    def subscribe(self, tokens: List[str], mode: str = "full"):
        # Fyers requires symbols in format "NSE:NIFTY..." or "MCX:GOLD..."
        # We need to map tokens to symbols using the provider
        
        symbols = []
        for token in tokens:
            inst = self.instrument_provider.get_instrument_by_token(token)
            if inst:
                symbols.append(inst.symbol)
        
        if symbols:
            self.subscribed_tokens.extend(symbols)
            if self.ws:
                # data_type: SymbolData (Full), DepthUpdate (Depth)
                # Fyers uses "SymbolData" for full mode
                self.ws.subscribe(symbols=symbols, data_type="SymbolData")

    def on_tick(self, callback: Callable[[List[Tick]], None]):
        # self.ws.on_message = lambda msg: callback([self._normalize_tick(msg)])
        pass

    def connect(self):
        # self.ws = FyersWebsocket(...)
        # self.ws.connect()
        pass

    def _normalize_tick(self, data: Dict) -> Tick:
        return Tick(
            token=0, # Map back from symbol
            timestamp=datetime.fromtimestamp(data.get('timestamp', 0)),
            last_price=data.get('ltp', 0.0),
            volume=data.get('vol_traded_today', 0),
            oi=data.get('oi', 0),
            change=0.0
        )
