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
    
    def fetch_option_chain(self, symbol: str, expiry: str) -> Dict[str, Any]:
        """
        Fetch option chain from instruments with live quotes.
        Note: Fyers doesn't have a native option chain API, 
        so we build it from the instrument list and fetch live quotes.
        """
        try:
            import logging
            from fyers_apiv3 import fyersModel
            
            logger = logging.getLogger(__name__)
            
            # Get all instruments
            instruments = self.instrument_provider.fetch_instruments()
            
            # Filter for the specific symbol and expiry
            option_instruments = []
            for inst in instruments:
                if symbol in inst.symbol and inst.instrument_type in ["CE", "PE"]:
                    if inst.expiry:
                        inst_expiry = inst.expiry.strftime("%Y-%m-%d")
                        if inst_expiry == expiry:
                            option_instruments.append(inst)
            
            if not option_instruments:
                logger.warning(f"No option instruments found for {symbol} expiry {expiry}")
                return {}
            
            # Build list of symbols for quote fetch (limit to reasonable number)
            # Fyers allows max 50 symbols per quote request
            symbols_to_fetch = [inst.symbol for inst in option_instruments[:100]]  # Limit to 100 for performance
            
            # Fetch live quotes from Fyers
            quotes_data = {}
            try:
                # Create Fyers model for quotes
                fyers = fyersModel.FyersModel(client_id=self.client_id, is_async=False, token=self.access_token, log_path="")
                
                # Fetch quotes in batches of 50
                batch_size = 50
                for i in range(0, len(symbols_to_fetch), batch_size):
                    batch = symbols_to_fetch[i:i+batch_size]
                    symbols_str = ",".join(batch)
                    
                    quotes_response = fyers.quotes({"symbols": symbols_str})
                    
                    if quotes_response and quotes_response.get('s') == 'ok':
                        # Response 'd' can be either a dict or a list
                        response_data = quotes_response.get('d', {})
                        
                        if isinstance(response_data, dict):
                            # Dictionary format: {symbol: quote_data}
                            for quote_key, quote_val in response_data.items():
                                quotes_data[quote_key] = quote_val
                        elif isinstance(response_data, list):
                            # List format: [{symbol: ..., data: ...}, ...]
                            for quote_item in response_data:
                                if isinstance(quote_item, dict):
                                    symbol = quote_item.get('n', '')
                                    if symbol:
                                        quotes_data[symbol] = quote_item
                    
            except Exception as e:
                logger.warning(f"Error fetching live quotes from Fyers: {e}")
                # Continue with zero prices if quote fetch fails
            
            # Build option chain data structure with live prices
            option_data = []
            for inst in option_instruments[:100]:  # Match the limit above
                symbol_key = inst.symbol
                quote = quotes_data.get(symbol_key, {})
                
                option_data.append({
                    'symbol': inst.symbol,
                    'strike_price': inst.strike,
                    'option_type': inst.instrument_type,
                    'ltp': quote.get('v', {}).get('lp', 0.0) if quote else 0.0,  # Last price
                    'oi': quote.get('v', {}).get('oi', 0) if quote else 0,  # Open interest
                    'volume': quote.get('v', {}).get('volume', 0) if quote else 0,  # Volume
                    'token': inst.token,
                    'expiry': expiry
                })
            
            # Sort by strike price
            option_data.sort(key=lambda x: x['strike_price'])
            
            # Try to get spot price from underlying index
            spot_price = 0
            try:
                if symbol == "NIFTY":
                    spot_symbol = "NSE:NIFTY50-INDEX"
                elif symbol == "BANKNIFTY":
                    spot_symbol = "NSE:NIFTYBANK-INDEX"
                else:
                    spot_symbol = f"NSE:{symbol}-INDEX"
                
                spot_response = fyers.quotes({"symbols": spot_symbol})
                if spot_response and spot_response.get('s') == 'ok':
                    spot_data = spot_response.get('d', {}).get(spot_symbol, {})
                    spot_price = spot_data.get('v', {}).get('lp', 0)
            except:
                pass
            
            return {
                'data': option_data,
                'spot_price': spot_price,
                'pcr': 0,  # Calculate if needed
                'symbol': symbol,
                'expiry': expiry
            }
            
        except Exception as e:
            logging.error(f"Error fetching Fyers option chain: {e}")
            import traceback
            traceback.print_exc()
            return {}
