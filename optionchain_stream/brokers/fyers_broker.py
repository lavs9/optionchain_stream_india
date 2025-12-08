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
        Fetch option chain using Fyers native optionchain API.
        This provides complete option chain data with live prices.
        """
        try:
            import logging
            from fyers_apiv3 import fyersModel
            from datetime import datetime
            
            logger = logging.getLogger(__name__)
            
            # Create Fyers model
            fyers = fyersModel.FyersModel(client_id=self.client_id, is_async=False, token=self.access_token, log_path="")
            
            # Map symbol to Fyers format
            # NIFTY -> NSE:NIFTY50-INDEX, BANKNIFTY -> NSE:NIFTYBANK-INDEX
            if symbol == "NIFTY":
                fyers_symbol = "NSE:NIFTY50-INDEX"
            elif symbol == "BANKNIFTY":
                fyers_symbol = "NSE:NIFTYBANK-INDEX"
            else:
                fyers_symbol = f"NSE:{symbol}-INDEX"
            
            # Convert expiry to timestamp
            # Fyers expects Unix timestamp in seconds
            try:
                expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
                # Set to end of day (3:30 PM IST for Indian market)
                expiry_dt = expiry_dt.replace(hour=15, minute=30)
                expiry_timestamp = str(int(expiry_dt.timestamp()))
            except Exception as e:
                logger.warning(f"Error parsing expiry date: {e}")
                expiry_timestamp = ""
            
            # Prepare request data
            data = {
                "symbol": fyers_symbol,
                "strikecount": 25,  # Get 25 strikes on each side
                "timestamp": expiry_timestamp
            }
            
            logger.info(f"Fetching Fyers option chain with data: {data}")
            
            # Call Fyers option chain API
            response = fyers.optionchain(data=data)
            
            if not response or response.get('s') != 'ok':
                logger.error(f"Fyers option chain API error: {response}")
                return {}
            
            # Parse response
            option_chain_data = response.get('data', {})
            if not option_chain_data:
                logger.warning("No option chain data in response")
                return {}
            
            # Get options data
            options_data = option_chain_data.get('optionsChain', [])
            spot_price = option_chain_data.get('ltp', 0)
            
            # Build standardized option chain format
            option_data = []
            for option_item in options_data:
                # Each item has 'call' and 'put' data
                strike = option_item.get('strike_price', 0)
                
                call_data = option_item.get('call', {})
                put_data = option_item.get('put', {})
                
                # Add call option
                if call_data:
                    option_data.append({
                        'symbol': call_data.get('symbol', ''),
                        'strike_price': strike,
                        'option_type': 'CE',
                        'ltp': call_data.get('ltp', 0.0),
                        'oi': call_data.get('oi', 0),
                        'volume': call_data.get('volume', 0),
                        'bid': call_data.get('bid', 0.0),
                        'ask': call_data.get('ask', 0.0),
                        'option_greeks': {
                            'iv': call_data.get('iv', 0),
                            'delta': call_data.get('delta', 0),
                            'gamma': call_data.get('gamma', 0),
                            'theta': call_data.get('theta', 0),
                            'vega': call_data.get('vega', 0)
                        } if 'iv' in call_data else {},
                        'expiry': expiry
                    })
                
                # Add put option
                if put_data:
                    option_data.append({
                        'symbol': put_data.get('symbol', ''),
                        'strike_price': strike,
                        'option_type': 'PE',
                        'ltp': put_data.get('ltp', 0.0),
                        'oi': put_data.get('oi', 0),
                        'volume': put_data.get('volume', 0),
                        'bid': put_data.get('bid', 0.0),
                        'ask': put_data.get('ask', 0.0),
                        'option_greeks': {
                            'iv': put_data.get('iv', 0),
                            'delta': put_data.get('delta', 0),
                            'gamma': put_data.get('gamma', 0),
                            'theta': put_data.get('theta', 0),
                            'vega': put_data.get('vega', 0)
                        } if 'iv' in put_data else {},
                        'expiry': expiry
                    })
            
            # Sort by strike price
            option_data.sort(key=lambda x: x['strike_price'])
            
            # Calculate PCR if possible
            total_call_oi = sum(opt['oi'] for opt in option_data if opt['option_type'] == 'CE')
            total_put_oi = sum(opt['oi'] for opt in option_data if opt['option_type'] == 'PE')
            pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0
            
            logger.info(f"Fyers option chain: {len(option_data)} contracts, spot: {spot_price}, PCR: {pcr:.2f}")
            
            return {
                'data': option_data,
                'spot_price': spot_price,
                'pcr': pcr,
                'symbol': symbol,
                'expiry': expiry
            }
            
        except Exception as e:
            logging.error(f"Error fetching Fyers option chain: {e}")
            import traceback
            traceback.print_exc()
            return {}
