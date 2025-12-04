import requests
import pandas as pd
from typing import List, Dict
from datetime import datetime
from optionchain_stream.models import Instrument
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider

class ZerodhaInstrumentProvider(InstrumentProvider):
    def __init__(self):
        self.url = "https://api.kite.trade/instruments"
        self.instruments_map: Dict[int, Instrument] = {}
        self.symbol_map: Dict[str, Instrument] = {}

    def fetch_instruments(self, exchange: str = 'NFO') -> List[Instrument]:
        print("Fetching Zerodha instruments...")
        df = pd.read_csv(self.url)
        
        instruments = []
        for _, row in df.iterrows():
            if row['exchange'] != exchange:
                continue
                
            try:
                expiry = datetime.strptime(row['expiry'], '%Y-%m-%d') if pd.notna(row['expiry']) else None
            except:
                expiry = None

            inst = Instrument(
                exchange=row['exchange'],
                token=str(row['instrument_token']),
                symbol=row['tradingsymbol'],
                name=row['name'],
                expiry=expiry,
                strike=float(row['strike']),
                lot_size=int(row['lot_size']),
                instrument_type=row['instrument_type'],
                broker_token=str(row['instrument_token']),
                tick_size=float(row['tick_size'])
            )
            instruments.append(inst)
            self.instruments_map[inst.token] = inst
            self.symbol_map[inst.symbol] = inst
            
        return instruments

    def get_instrument_by_token(self, token: str) -> Instrument:
        return self.instruments_map.get(token)

    def get_instrument_by_symbol(self, symbol: str) -> Instrument:
        return self.symbol_map.get(symbol)
