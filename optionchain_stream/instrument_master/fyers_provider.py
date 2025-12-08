import requests
import pandas as pd
import io
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from optionchain_stream.models import Instrument
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider
from optionchain_stream.instrument_cache import InstrumentCache

class FyersInstrumentProvider(InstrumentProvider):
    # Class-level cache shared across instances
    _cache = InstrumentCache(cache_ttl_seconds=3600)
    
    def __init__(self):
        """Initialize Fyers instrument provider with Redis caching"""
        self.urls = {
            'NSE_FO': "https://public.fyers.in/sym_details/NSE_FO.csv",
            'NSE_EQ': "https://public.fyers.in/sym_details/NSE_CM.csv",
            'MCX': "https://public.fyers.in/sym_details/MCX_COM.csv"
        }
        self.instruments_map: Dict[str, Instrument] = {}
        self.symbol_map: Dict[str, Instrument] = {}
        self.cache_key = "fyers_instruments"

    def fetch_instruments(self, exchange: str = 'NSE') -> List[Instrument]:
        """
        Fetch instruments with Redis caching support.
        Returns cached data if available and not expired.
        """
        # Try to get from cache first
        cached = self._cache.get(self.cache_key)
        if cached:
            # Rebuild maps from cached data
            self.instruments_map = {inst.token: inst for inst in cached}
            self.symbol_map = {inst.symbol: inst for inst in cached}
            return cached
        
        # Cache miss - fetch from CSV files
        print("📥 Fetching Fyers instruments from CSV files...")
        instruments = []
        
        for exch_key, url in self.urls.items():
            print(f"  Downloading {exch_key}...")
            try:
                # Fyers CSV has no header
                df = pd.read_csv(url, header=None)
                
                for _, row in df.iterrows():
                    # Mapping based on inspection:
                    # 0: Token, 1: Name, 3: Lot, 4: Tick, 8: Expiry (Unix), 9: Symbol, 13: Underlying, 15: Strike, 16: Option Type
                    
                    try:
                        expiry = datetime.fromtimestamp(int(row[8])) if pd.notna(row[8]) and row[8] > 0 else None
                    except:
                        expiry = None

                    # Determine exchange from URL key or column 10 (Exchange ID)
                    exch_id = row[10]
                    exch_name = 'NSE'
                    if exch_id == 10: exch_name = 'NSE'
                    elif exch_id == 11: exch_name = 'MCX'
                    elif exch_id == 12: exch_name = 'BSE'
                    
                    # Refine exchange name (FO vs EQ)
                    if exch_key == 'NSE_FO': exch_name = 'NSE_FO'
                    elif exch_key == 'MCX': exch_name = 'MCX'
                    
                    inst = Instrument(
                        exchange=exch_name,
                        token=str(row[0]),
                        symbol=str(row[9]), # Fyers symbol format e.g. NSE:NIFTY...
                        name=str(row[1]),
                        expiry=expiry,
                        strike=float(row[15]) if len(row) > 15 and pd.notna(row[15]) else 0.0,
                        lot_size=int(row[3]) if pd.notna(row[3]) else 0,
                        instrument_type=str(row[16]) if len(row) > 16 and pd.notna(row[16]) else '',
                        broker_token=str(row[0]),
                        tick_size=float(row[4]) if pd.notna(row[4]) else 0.05
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
        """Clear the instrument cache to force re-fetch"""
        cls._cache.clear("fyers_instruments")

    def get_instrument_by_token(self, token: int) -> Instrument:
        # Ensure instruments are loaded
        if not self.instruments_map:
            self.fetch_instruments()
        return self.instruments_map.get(token)

    def get_instrument_by_symbol(self, symbol: str) -> Instrument:
        # Ensure instruments are loaded
        if not self.symbol_map:
            self.fetch_instruments()
        return self.symbol_map.get(symbol)
