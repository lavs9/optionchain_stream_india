import requests
import pandas as pd
import gzip
import json
import io
from typing import List, Dict
from datetime import datetime
from optionchain_stream.models import Instrument
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider

class UpstoxInstrumentProvider(InstrumentProvider):
    def __init__(self):
        # Upstox provides separate files for exchanges. Assuming NSE for now.
        self.url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
        self.instruments_map: Dict[int, Instrument] = {}
        self.symbol_map: Dict[str, Instrument] = {}

    def fetch_instruments(self, exchange: str = 'NSE_FO') -> List[Instrument]:
        urls = [
            "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz",
            "https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz"
        ]
        
        instruments = []
        for url in urls:
            print(f"Fetching instruments from {url}...")
            try:
                response = requests.get(url)
                content = gzip.decompress(response.content)
                data = json.loads(content)
                
                for item in data:
                    try:
                        expiry = datetime.fromtimestamp(item.get('expiry')/1000) if item.get('expiry') else None
                    except:
                        expiry = None
        
                    inst = Instrument(
                        exchange=item.get('exchange'),
                        token=item.get('instrument_key'),
                        symbol=item.get('trading_symbol'),
                        name=item.get('name'),
                        expiry=expiry,
                        strike=float(item.get('strike_price', 0)),
                        lot_size=int(item.get('lot_size', 0)),
                        instrument_type=item.get('instrument_type'),
                        broker_token=item.get('instrument_key'),
                        tick_size=float(item.get('tick_size', 0.05))
                    )
                    instruments.append(inst)
                    self.instruments_map[inst.token] = inst
                    self.symbol_map[inst.symbol] = inst
            except Exception as e:
                print(f"Error fetching/parsing {url}: {e}")
            
        return instruments

    def get_instrument_by_token(self, token: str) -> Instrument:
        return self.instruments_map.get(token)

    def get_instrument_by_symbol(self, symbol: str) -> Instrument:
        return self.symbol_map.get(symbol)
