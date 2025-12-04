import logging
import upstox_client
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3
from typing import List, Dict, Any, Callable
from datetime import datetime
from optionchain_stream.broker_interface import Broker
from optionchain_stream.models import Tick
from optionchain_stream.instrument_master.upstox_provider import UpstoxInstrumentProvider
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider

class UpstoxBroker(Broker):
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, access_token: str = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.instrument_provider = UpstoxInstrumentProvider()
        self.callbacks = []
        self.streamer = None

    def authenticate(self):
        if not self.access_token:
            raise ValueError("Access token required. Please generate one using the auth flow.")
        
        conf = upstox_client.Configuration()
        conf.access_token = self.access_token
        self.api_client = upstox_client.ApiClient(conf)
        self.streamer = MarketDataStreamerV3(self.api_client)
        
        # Register callbacks
        self.streamer.on("message", self._on_market_data_handler)
        self.streamer.on("open", lambda: logging.info("Upstox WebSocket Opened"))
        self.streamer.on("close", lambda: logging.info("Upstox WebSocket Closed"))
        self.streamer.on("error", lambda error: logging.error(f"Upstox WebSocket Error: {error}"))

    def get_instrument_provider(self) -> InstrumentProvider:
        return self.instrument_provider

    def subscribe(self, tokens: List[str], mode: str = "full"):
        if not self.streamer:
            self.authenticate()
            
        # Map mode to Upstox mode
        upstox_mode = "full" if mode == "full" else "ltpc"
        
        # Subscribe
        self.streamer.subscribe(tokens, mode=upstox_mode)

    def on_tick(self, callback: Callable[[List[Tick]], None]):
        self.callbacks.append(callback)

    def connect(self):
        if not self.streamer:
            self.authenticate()
        self.streamer.connect()
    
    def _on_market_data_handler(self, data):
        # data is likely a protobuf object or dict. SDK usually decodes it.
        # Assuming data is a dict or object with fields.
        # We need to handle both single tick or list of ticks if SDK batches them.
        # Based on typical SDKs, it might be a single update or a map.
        
        # logging.info(f"Raw Data: {data}")
        
        # If data is not a list, wrap it
        if not isinstance(data, list):
            data = [data]
            
        normalized_ticks = []
        for tick_data in data:
            # Check if tick_data is object or dict
            # SDK v3 usually returns objects or dicts. Let's assume dict for safety or try to access attrs.
            # We'll try to convert to dict if it's an object
            if hasattr(tick_data, 'to_dict'):
                d = tick_data.to_dict()
            else:
                d = tick_data
            
            # logging.info(f"Processed Dict: {d}")
            
            # Ignore market_info
            if d.get('type') == 'market_info':
                continue
                
            normalized_ticks.append(self._normalize_tick(d))
            
        for callback in self.callbacks:
            callback(normalized_ticks)

    def _normalize_tick(self, data: Dict) -> Tick:
        # Map Upstox data to Tick
        # Fields depend on the mode (full vs ltpc)
        # Assuming 'full' mode fields
        
        # Extract timestamp
        ts = datetime.now()
        if 'timestamp' in data and data['timestamp']:
             # Upstox timestamp might be in ms
             try:
                 ts = datetime.fromtimestamp(int(data['timestamp']) / 1000)
             except:
                 pass

        return Tick(
            token=data.get('instrument_token') or data.get('instrument_key', '0'),
            timestamp=ts,
            last_price=float(data.get('ltp', 0.0) or data.get('last_price', 0.0)),
            volume=int(data.get('volume', 0) or data.get('vol', 0)),
            oi=int(data.get('oi', 0) or data.get('open_interest', 0)),
            change=0.0, # Calculate if needed or extract
            bid_price=float(data.get('depth', {}).get('buy', [{}])[0].get('price', 0.0)) if 'depth' in data else 0.0,
            ask_price=float(data.get('depth', {}).get('sell', [{}])[0].get('price', 0.0)) if 'depth' in data else 0.0,
            bid_qty=int(data.get('depth', {}).get('buy', [{}])[0].get('quantity', 0)) if 'depth' in data else 0,
            ask_qty=int(data.get('depth', {}).get('sell', [{}])[0].get('quantity', 0)) if 'depth' in data else 0
        )

    def fetch_option_chain(self, symbol: str, expiry: str) -> Dict[str, Any]:
        """
        Fetch option chain from Upstox.
        Note: Upstox API for option chain might require specific parameters.
        This is a placeholder for the actual API call.
        """
        if not self.api_client:
            self.authenticate()
            
        # Example: self.api_client.call_api(...)
        # For now return empty dict as we need to research the exact endpoint
        return {}
