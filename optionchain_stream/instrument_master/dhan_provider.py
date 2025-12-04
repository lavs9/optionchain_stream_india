import requests
import pandas as pd
import io
from typing import List, Dict
from datetime import datetime
from optionchain_stream.models import Instrument
from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider

class DhanInstrumentProvider(InstrumentProvider):
    def __init__(self):
        self.url = "https://images.dhan.co/api-data/api-scrip-master.csv"
        self.instruments_map: Dict[str, Instrument] = {}
        self.symbol_map: Dict[str, Instrument] = {}

    def fetch_instruments(self, exchange: str = 'NSE') -> List[Instrument]:
        print("Fetching Dhan instruments...")
        try:
            df = pd.read_csv(self.url)
        except Exception as e:
            print(f"Error fetching Dhan instruments: {e}")
            return []
            
        instruments = []
        for _, row in df.iterrows():
            # Filter by exchange if needed, but Dhan CSV has all.
            # We can filter later or store all.
            
            # Parse expiry
            expiry = None
            if pd.notna(row['SEM_EXPIRY_DATE']):
                try:
                    # Format likely '2023-10-26 14:30:00' or similar
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
                exchange = 'MCX' # Usually MCX is derivatives

            inst = Instrument(
                exchange=exchange,
                token=str(row['SEM_SMST_SECURITY_ID']),
                symbol=str(row['SEM_TRADING_SYMBOL']),
                name=str(row['SEM_INSTRUMENT_NAME']), # or similar
                expiry=None, # Need to parse date string
                strike=float(row['SEM_STRIKE_PRICE']),
                lot_size=int(row['SEM_LOT_UNITS']),
                instrument_type=row['SEM_INSTRUMENT_NAME'],
                broker_token=str(row['SEM_SMST_SECURITY_ID']),
                tick_size=float(row['SEM_TICK_SIZE'])
            )
            instruments.append(inst)
            self.instruments_map[inst.token] = inst
            self.symbol_map[inst.symbol] = inst
            
        return instruments

    def get_instrument_by_token(self, token: int) -> Instrument:
        return self.instruments_map.get(token)

    def get_instrument_by_symbol(self, symbol: str) -> Instrument:
        return self.symbol_map.get(symbol)
