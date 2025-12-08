import requests
import pandas as pd
import gzip
import json
import io
from typing import List, Dict
from datetime import datetime
from optionchain_stream.models import Instrument
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider
from optionchain_stream.instrument_cache import InstrumentCache

class UpstoxInstrumentProvider(InstrumentProvider):
    # Class-level cache shared across instances
    _cache = InstrumentCache(cache_ttl_seconds=3600)
    
    def __init__(self):
        self.url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
        self.instruments_map: Dict[int, Instrument] = {}
        self.symbol_map: Dict[str, Instrument] = {}
        self.cache_key = "upstox_instruments"

    def fetch_instruments(self, exchange: str = 'NSE_FO') -> List[Instrument]:
        """Fetch instruments with Redis caching support"""
        # Try cache first
        cached = self._cache.get(self.cache_key)
        if cached:
            self.instruments_map = {inst.token: inst for inst in cached}
            self.symbol_map = {inst.symbol: inst for inst in cached}
            return cached
        
        # Cache miss - fetch from URLs
        urls = [
            "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz",
            "https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz"
        ]
        
        instruments = []
        print("📥 Fetching Upstox instruments...")
        for url in urls:
            print(f"  Downloading from {url}...")
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
                        exchange=item.get('segment'),
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
                print(f"❌ Error fetching/parsing {url}: {e}")
        
        # Store in cache
        if instruments:
            self._cache.set(self.cache_key, instruments)
            
        return instruments
    
    @classmethod
    def clear_cache(cls):
        """Clear the instrument cache"""
        cls._cache.clear("upstox_instruments")

    def get_instrument_by_token(self, token: str) -> Instrument:
        if not self.instruments_map:
            self.fetch_instruments()
        return self.instruments_map.get(token)

    def get_instrument_by_symbol(self, symbol: str) -> Instrument:
        if not self.symbol_map:
            self.fetch_instruments()
        return self.symbol_map.get(symbol)
