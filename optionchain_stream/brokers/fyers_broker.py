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
            if symbol == "NIFTY":
                fyers_symbol = "NSE:NIFTY50-INDEX"
            elif symbol == "BANKNIFTY":
                fyers_symbol = "NSE:NIFTYBANK-INDEX"
            else:
                fyers_symbol = f"NSE:{symbol}-INDEX"
            
            # Convert expiry to timestamp if provided
            expiry_timestamp = ""
            if expiry:
                try:
                    expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
                    expiry_dt = expiry_dt.replace(hour=15, minute=30)
                    expiry_timestamp = str(int(expiry_dt.timestamp()))
                except Exception as e:
                    logger.warning(f"Error parsing expiry date: {e}")
            
            # Prepare request data
            data = {
                "symbol": fyers_symbol,
                "strikecount": 50,  # Get 50 strikes on each side
                "timestamp": expiry_timestamp
            }
            
            logger.info(f"Fetching Fyers option chain with data: {data}")
            
            # Call Fyers option chain API
            response = fyers.optionchain(data=data)
            
            if not response or response.get('s') != 'ok':
                logger.error(f"Fyers option chain API error: {response}")
                return {}
            
            # Parse response
            response_data = response.get('data', {})
            if not response_data:
                logger.warning("No data in response")
                return {}
            
            # Get options chain array
            options_chain = response_data.get('optionsChain', [])
            
            # First item is the underlying index itself (strike_price: -1), skip it
            spot_price = 0
            if options_chain and options_chain[0].get('strike_price') == -1:
                spot_price = options_chain[0].get('ltp', 0)
                options_chain = options_chain[1:]  # Skip the index item
            
            # Build standardized option chain format
            option_data = []
            for option_item in options_chain:
                strike = option_item.get('strike_price', 0)
                option_type = option_item.get('option_type', '')
                
                # Skip if not a valid option
                if not option_type or option_type not in ['CE', 'PE']:
                    continue
                
                option_data.append({
                    'symbol': option_item.get('symbol', ''),
                    'strike_price': strike,
                    'option_type': option_type,
                    'ltp': option_item.get('ltp', 0.0),
                    'oi': option_item.get('oi', 0),
                    'volume': option_item.get('volume', 0),
                    'bid': option_item.get('bid', 0.0),
                    'ask': option_item.get('ask', 0.0),
                    'prev_oi': option_item.get('prev_oi', 0),
                    'oi_change': option_item.get('oich', 0),
                    'ltp_change': option_item.get('ltpch', 0),
                    'expiry': expiry
                })
            
            # Sort by strike price
            option_data.sort(key=lambda x: x['strike_price'])
            
            # Calculate PCR
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
