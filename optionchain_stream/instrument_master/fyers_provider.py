import requests
import pandas as pd
import io
from typing import List, Dict
from datetime import datetime
from optionchain_stream.models import Instrument
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider

class FyersInstrumentProvider(InstrumentProvider):
    def __init__(self):
        self.urls = {
            'NSE_FO': "https://public.fyers.in/sym_details/NSE_FO.csv",
            'NSE_EQ': "https://public.fyers.in/sym_details/NSE_CM.csv",
            'MCX': "https://public.fyers.in/sym_details/MCX_COM.csv"
        }
        self.instruments_map: Dict[str, Instrument] = {}
        self.symbol_map: Dict[str, Instrument] = {}

    def fetch_instruments(self, exchange: str = 'NSE') -> List[Instrument]:
        print("Fetching Fyers instruments...")
        instruments = []
        
        for exch_key, url in self.urls.items():
            print(f"Fetching from {url}...")
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
                print(f"Error fetching/parsing {url}: {e}")
            
        return instruments

    def get_instrument_by_token(self, token: int) -> Instrument:
        return self.instruments_map.get(token)

    def get_instrument_by_symbol(self, symbol: str) -> Instrument:
        return self.symbol_map.get(symbol)
