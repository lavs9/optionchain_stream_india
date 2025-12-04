import logging
from typing import List, Dict, Any, Callable
from datetime import datetime
from kiteconnect import KiteConnect, KiteTicker
from optionchain_stream.broker_interface import Broker
from optionchain_stream.models import Tick
from optionchain_stream.instrument_master.zerodha_provider import ZerodhaInstrumentProvider
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider

class ZerodhaBroker(Broker):
    def __init__(self, api_key: str, access_token: str):
        self.api_key = api_key
        self.access_token = access_token
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        self.kws = KiteTicker(api_key, access_token, debug=True)
        self.instrument_provider = ZerodhaInstrumentProvider()

    def authenticate(self):
        # Authentication handled externally or via init
        pass

    def get_instrument_provider(self) -> InstrumentProvider:
        return self.instrument_provider

    def subscribe(self, tokens: List[int], mode: str = "full"):
        if mode == "full":
            mode = self.kws.MODE_FULL
        elif mode == "ltp":
            mode = self.kws.MODE_LTP
        elif mode == "quote":
            mode = self.kws.MODE_QUOTE
        
        self.kws.subscribe(tokens)
        self.kws.set_mode(mode, tokens)

    def on_tick(self, callback: Callable[[List[Tick]], None]):
        def wrapper(ticks):
            normalized_ticks = []
            for tick in ticks:
                normalized_ticks.append(Tick(
                    token=str(tick['instrument_token']),
                    timestamp=tick.get('timestamp', datetime.now()),
                    last_price=tick.get('last_price', 0.0),
                    volume=tick.get('volume', 0),
                    oi=tick.get('oi', 0),
                    change=tick.get('change', 0.0),
                    bid_price=tick.get('depth', {}).get('buy', [{}])[0].get('price', 0.0) if 'depth' in tick else 0.0,
                    ask_price=tick.get('depth', {}).get('sell', [{}])[0].get('price', 0.0) if 'depth' in tick else 0.0,
                    bid_qty=tick.get('depth', {}).get('buy', [{}])[0].get('quantity', 0) if 'depth' in tick else 0,
                    ask_qty=tick.get('depth', {}).get('sell', [{}])[0].get('quantity', 0) if 'depth' in tick else 0
                ))
            callback(normalized_ticks)
            
        self.kws.on_ticks = lambda ws, ticks: wrapper(ticks)

    def connect(self):
        self.kws.connect()
