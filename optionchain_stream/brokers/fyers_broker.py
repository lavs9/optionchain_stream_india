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
        self._tick_callbacks: List[Callable[[List[Tick]], None]] = []
        self.subscribed_tokens = []
        self.logger = logging.getLogger(__name__)

    def authenticate(self):
        # Fyers auth is implicit via access_token passed to socket
        pass

    def get_instrument_provider(self) -> InstrumentProvider:
        return self.instrument_provider

    def subscribe(self, tokens: List[str], mode: str = "full"):
        # Fyers requires symbols in format "NSE:NIFTY..." or "MCX:GOLD..."
        # Accepts either our internal instrument tokens (resolved via the
        # instrument provider) or raw Fyers symbol strings directly.
        symbols = []
        for token in tokens:
            inst = self.instrument_provider.get_instrument_by_token(token)
            symbols.append(inst.symbol if inst else token)

        if symbols and self.ws:
            self.subscribed_tokens.extend(symbols)
            data_type = "SymbolUpdate" if mode == "full" else "DepthUpdate"
            self.ws.subscribe(symbols=symbols, data_type=data_type)

    def unsubscribe(self, tokens: List[str]):
        symbols = []
        for token in tokens:
            inst = self.instrument_provider.get_instrument_by_token(token)
            symbols.append(inst.symbol if inst else token)
        if symbols and self.ws:
            self.ws.unsubscribe(symbols=symbols, data_type="SymbolUpdate")
            for s in symbols:
                if s in self.subscribed_tokens:
                    self.subscribed_tokens.remove(s)

    def on_tick(self, callback: Callable[[List[Tick]], None]):
        self._tick_callbacks.append(callback)

    def _on_message(self, message: Dict):
        # Non-tick control/ack frames (type: cn/ful/sub/...) come through the
        # same on_message callback as real ticks. Only type "sf" is a symbol
        # feed update worth normalizing — skip everything else.
        if message.get('type') != 'sf':
            self.logger.debug(f"Ignoring non-tick Fyers WS message: {message}")
            return
        try:
            tick = self._normalize_tick(message)
        except Exception:
            self.logger.exception(f"Failed to normalize Fyers WS message: {message}")
            return
        for callback in self._tick_callbacks:
            callback([tick])

    def _on_error(self, message):
        self.logger.error(f"Fyers WS error: {message}")

    def _on_connect(self):
        self.logger.info("Fyers WS connected")

    def _on_close(self, message):
        self.logger.warning(f"Fyers WS closed: {message}")

    def connect(self):
        combined_token = f"{self.client_id}:{self.access_token}"
        self.ws = data_ws.FyersDataSocket(
            access_token=combined_token,
            log_path="",
            litemode=False,
            write_to_file=False,
            reconnect=True,
            on_connect=self._on_connect,
            on_close=self._on_close,
            on_error=self._on_error,
            on_message=self._on_message,
        )
        self.ws.connect()

    def _normalize_tick(self, data: Dict) -> Tick:
        return Tick(
            token=data.get('fy_token', data.get('symbol', '')),
            timestamp=datetime.fromtimestamp(data.get('last_traded_time', 0)) if data.get('last_traded_time') else datetime.now(),
            last_price=data.get('ltp', 0.0),
            volume=data.get('vol_traded_today', 0),
            oi=data.get('oi', 0),
            change=data.get('ch', 0.0),
            bid_price=data.get('bid_price', 0.0),
            ask_price=data.get('ask_price', 0.0),
            bid_qty=data.get('bid_size', 0),
            ask_qty=data.get('ask_size', 0),
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
            
            # Map symbol to Fyers format. Indices use -INDEX on their own
            # exchange (NSE or BSE); anything else is treated as an equity
            # underlying on NSE, which needs -EQ, not -INDEX.
            INDEX_SYMBOLS = {
                "NIFTY": "NSE:NIFTY50-INDEX",
                "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
                "FINNIFTY": "NSE:FINNIFTY-INDEX",
                "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
                "SENSEX": "BSE:SENSEX-INDEX",
                "BANKEX": "BSE:BANKEX-INDEX",
            }
            if symbol in INDEX_SYMBOLS:
                fyers_symbol = INDEX_SYMBOLS[symbol]
            else:
                fyers_symbol = f"NSE:{symbol}-EQ"
            
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
                    # Price data
                    'ltp': option_item.get('ltp', 0.0),
                    'ltpch': option_item.get('ltpch', 0.0),  # LTP change
                    'ltpchp': option_item.get('ltpchp', 0.0),  # LTP change %
                    'bid': option_item.get('bid', 0.0),
                    'ask': option_item.get('ask', 0.0),
                    # Open Interest data
                    'oi': option_item.get('oi', 0),
                    'prev_oi': option_item.get('prev_oi', 0),
                    'oich': option_item.get('oich', 0),  # OI change
                    'oichp': option_item.get('oichp', 0.0),  # OI change %
                    # Volume
                    'volume': option_item.get('volume', 0),
                    # Future price data (if available)
                    'fp': option_item.get('fp', 0.0),  # Future price
                    'fpch': option_item.get('fpch', 0.0),  # Future price change
                    'fpchp': option_item.get('fpchp', 0.0),  # Future price change %
                    # Metadata
                    'fytoken': option_item.get('fyToken', ''),
                    'description': option_item.get('description', ''),
                    'ex_symbol': option_item.get('ex_symbol', ''),
                    'exchange': option_item.get('exchange', ''),
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
