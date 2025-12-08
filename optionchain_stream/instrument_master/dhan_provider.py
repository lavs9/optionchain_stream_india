import requests
import pandas as pd
import io
from typing import List, Dict
from datetime import datetime
from optionchain_stream.models import Instrument
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider
from optionchain_stream.instrument_cache import InstrumentCache

class DhanInstrumentProvider(InstrumentProvider):
    # Class-level cache shared across instances
    _cache = InstrumentCache(cache_ttl_seconds=3600)
    
    def __init__(self):
        self.url = "https://images.dhan.co/api-data/api-scrip-master.csv"
        self.instruments_map: Dict[str, Instrument] = {}
        self.symbol_map: Dict[str, Instrument] = {}
        self.cache_key = "dhan_instruments"

    def fetch_instruments(self, exchange: str = 'NSE') -> List[Instrument]:
        """Fetch instruments with Redis caching support"""
        # Try cache first
        cached = self._cache.get(self.cache_key)
        if cached:
            self.instruments_map = {inst.token: inst for inst in cached}
            self.symbol_map = {inst.symbol: inst for inst in cached}
            return cached
        
        # Cache miss - fetch from CSV
        print("📥 Fetching Dhan instruments from CSV...")
        try:
            df = pd.read_csv(self.url)
        except Exception as e:
            print(f"❌ Error fetching Dhan instruments: {e}")
            return []
            
        instruments = []
        for _, row in df.iterrows():
            # Parse expiry
            expiry = None
            if pd.notna(row['SEM_EXPIRY_DATE']):
                try:
                    expiry = pd.to_datetime(row['SEM_EXPIRY_DATE']).to_pydatetime()
                except:
                    pass

            # Map Exchange and Segment to standardized exchange name
            exch_id = str(row['SEM_EXM_EXCH_ID'])
            segment = str(row['SEM_SEGMENT'])
            
            exchange = exch_id
            if exch_id == 'NSE':
                if segment == 'D': exchange = 'NSE_FO'
                elif segment == 'E': exchange = 'NSE_EQ'
                elif segment == 'C': exchange = 'NSE_CD'
                elif segment == 'I': exchange = 'NSE_INDEX'
            elif exch_id == 'BSE':
                if segment == 'D': exchange = 'BSE_FO'
                elif segment == 'E': exchange = 'BSE_EQ'
                elif segment == 'C': exchange = 'BSE_CD'
                elif segment == 'I': exchange = 'BSE_INDEX'
            elif exch_id == 'MCX':
                exchange = 'MCX'

            inst = Instrument(
                exchange=exchange,
                token=str(row['SEM_SMST_SECURITY_ID']),
                symbol=str(row['SEM_TRADING_SYMBOL']),
                name=str(row['SEM_INSTRUMENT_NAME']),
                expiry=None,
                strike=float(row['SEM_STRIKE_PRICE']),
                lot_size=int(row['SEM_LOT_UNITS']),
                instrument_type=row['SEM_INSTRUMENT_NAME'],
                broker_token=str(row['SEM_SMST_SECURITY_ID']),
                tick_size=float(row['SEM_TICK_SIZE'])
            )
            instruments.append(inst)
            self.instruments_map[inst.token] = inst
            self.symbol_map[inst.symbol] = inst
        
        # Store in cache
        if instruments:
            self._cache.set(self.cache_key, instruments)
            
        return instruments
    
    @classmethod
    def clear_cache(cls):
        """Clear the instrument cache"""
        cls._cache.clear("dhan_instruments")

    def get_instrument_by_token(self, token: int) -> Instrument:
        if not self.instruments_map:
            self.fetch_instruments()
        return self.instruments_map.get(token)

    def get_instrument_by_symbol(self, symbol: str) -> Instrument:
        if not self.symbol_map:
            self.fetch_instruments()
        return self.symbol_map.get(symbol)
