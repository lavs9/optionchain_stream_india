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
        self.subscribed_tokens = set()
        self.api_client = None

    def authenticate(self):
        if not self.access_token:
            raise ValueError("Access token required. Please generate one using the auth flow.")
        
        conf = upstox_client.Configuration()
        conf.access_token = self.access_token
        self.api_client = upstox_client.ApiClient(conf)
        self.streamer = MarketDataStreamerV3(self.api_client)
        
        # Register callbacks
        self.streamer.on("message", self._on_market_data_handler)
        self.streamer.on("open", self._on_open)
        self.streamer.on("close", lambda code, reason: logging.info(f"Upstox WebSocket Closed: {code} {reason}"))
        self.streamer.on("error", lambda error: logging.error(f"Upstox WebSocket Error: {error}"))

    def _on_open(self):
        logging.info("Upstox WebSocket Opened")
        if self.subscribed_tokens:
            logging.info(f"Resubscribing to {len(self.subscribed_tokens)} tokens")
            # Convert set back to list
            tokens = list(self.subscribed_tokens)
            # We need to know the mode. Assuming 'full' for now or we need to store mode per token.
            # For simplicity, let's assume one mode for all or default to full.
            self.streamer.subscribe(tokens, mode="full")

    def get_instrument_provider(self) -> InstrumentProvider:
        return self.instrument_provider

    def subscribe(self, tokens: List[str], mode: str = "full"):
        if not self.streamer:
            self.authenticate()
            
        # Add to local cache
        for t in tokens:
            self.subscribed_tokens.add(t)
            
        # Map mode to Upstox mode
        upstox_mode = "full" if mode == "full" else "ltpc"
        
        # Try to subscribe immediately if connected (how to check? just try)
        try:
            self.streamer.subscribe(tokens, mode=upstox_mode)
        except Exception as e:
            logging.warning(f"Subscribe failed (will retry on open): {e}")

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
            
            # Debug: Print keys if it looks empty
            # logging.info(f"Tick Keys: {d.keys()}")
            
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
        
        # Debug type
        # logging.info(f"Data Type: {type(data)}")
        
        # Helper to get value from dict or object
        def get_val(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        # Extract timestamp
        ts = datetime.now()
        raw_ts = get_val(data, 'timestamp') or get_val(data, 'ltt')
        if raw_ts:
             try:
                 ts = datetime.fromtimestamp(int(raw_ts) / 1000)
             except:
                 pass
        
        token = get_val(data, 'instrument_token') or get_val(data, 'instrument_key') or '0'
        ltp = float(get_val(data, 'ltp') or get_val(data, 'last_price') or 0.0)
        vol = int(get_val(data, 'volume') or get_val(data, 'vol') or get_val(data, 'v') or 0)
        oi = int(get_val(data, 'oi') or get_val(data, 'open_interest') or 0)
        
        if token == '0' or ltp == 0.0:
            logging.warning(f"Empty Tick Data (Type: {type(data)}): {data}")

        return Tick(
            token=token,
            timestamp=ts,
            last_price=ltp,
            volume=vol,
            oi=oi,
            change=0.0, # Calculate if needed or extract
            bid_price=0.0, # Simplify for now
            ask_price=0.0,
            bid_qty=0,
            ask_qty=0
        )

    def fetch_option_chain(self, symbol: str, expiry: str) -> Dict[str, Any]:
        """
        Fetch option chain from Upstox.
        Uses the 'get_option_chain' or 'get_market_quote_ohlc' API.
        
        Args:
            symbol: Underlying symbol (e.g., 'NIFTY', 'BANKNIFTY')
            expiry: Expiry date in YYYY-MM-DD format.
        
        Returns:
            Dict containing option chain data with Greeks.
        """
        if not self.api_client:
            self.authenticate()
            
        try:
            # Upstox SDK usually has a method to get option chain
            # We need to construct the instrument key for the underlying
            # For NIFTY, it might be 'NSE_INDEX|Nifty 50'
            
            instrument_key = symbol
            # Simple mapping for common indices
            if symbol == 'NIFTY': instrument_key = 'NSE_INDEX|Nifty 50'
            elif symbol == 'BANKNIFTY': instrument_key = 'NSE_INDEX|Nifty Bank'
            
            # Call API (using generic call if specific method not found in inspection)
            # Based on docs: api_instance.get_put_call_option_chain_details(instrument_key, expiry_date)
            
            # We need to import the API class
            from upstox_client.api.options_api import OptionsApi
            options_api = OptionsApi(self.api_client)
            
            response = options_api.get_put_call_option_chain(
                instrument_key=instrument_key,
                expiry_date=expiry
            )
            
            # Convert response to dict
            if hasattr(response, 'to_dict'):
                return response.to_dict()
            return response
            
        except Exception as e:
            logging.error(f"Error fetching Upstox option chain: {e}")
            return {}
