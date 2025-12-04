from typing import Dict, Any, List
from datetime import datetime
from optionchain_stream.storage_interface import Storage
from optionchain_stream.models import Tick
import logging

try:
    from clickhouse_driver import Client
except ImportError:
    Client = None

class ClickHouseStorage(Storage):
    def __init__(self, host='localhost', port=9000, user='default', password='', database='default', batch_size=1000):
        if Client is None:
            logging.warning("clickhouse-driver not installed. ClickHouseStorage will not work.")
            self.client = None
        else:
            self.client = Client(host=host, port=port, user=user, password=password, database=database)
            self._init_db()
        
        self.buffer = []
        self.batch_size = batch_size

    def _init_db(self):
        if self.client:
            self.client.execute('''
                CREATE TABLE IF NOT EXISTS option_ticks (
                    timestamp DateTime,
                    symbol String,
                    token String,
                    last_price Float64,
                    volume UInt64,
                    oi UInt64,
                    change Float64,
                    bid_price Float64,
                    ask_price Float64,
                    bid_qty UInt32,
                    ask_qty UInt32
                ) ENGINE = MergeTree()
                ORDER BY (symbol, token, timestamp)
            ''')

    def store_tick(self, symbol: str, token: int, data: Tick):
        if not self.client:
            return

        row = {
            'timestamp': data.timestamp,
            'symbol': symbol,
            'token': token,
            'last_price': data.last_price,
            'volume': data.volume,
            'oi': data.oi,
            'change': data.change,
            'bid_price': data.bid_price if data.bid_price is not None else 0.0,
            'ask_price': data.ask_price if data.ask_price is not None else 0.0,
            'bid_qty': data.bid_qty if data.bid_qty is not None else 0,
            'ask_qty': data.ask_qty if data.ask_qty is not None else 0
        }
        self.buffer.append(row)
        
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self):
        if not self.client or not self.buffer:
            return
        
        try:
            self.client.execute('INSERT INTO option_ticks (timestamp, symbol, token, last_price, volume, oi, change, bid_price, ask_price, bid_qty, ask_qty) VALUES', self.buffer)
            self.buffer = []
        except Exception as e:
            logging.error(f"Failed to flush to ClickHouse: {e}")

    def get_option_chain(self, symbol: str) -> List[Dict[str, Any]]:
        return []

    def store_instruments(self, symbol: str, data: Any):
        pass

    def get_instrument(self, token: int) -> Dict[str, Any]:
        pass
