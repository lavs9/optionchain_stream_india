import redis
import json
from typing import Dict, Any, List
from optionchain_stream.storage_interface import Storage
from optionchain_stream.models import Tick
from dataclasses import asdict

class RedisStorage(Storage):
    def __init__(self, host='localhost', port=6379, db=0):
        self.conn = redis.StrictRedis(host=host, port=port, db=db)

    def store_tick(self, symbol: str, token: str, data: Tick):
        optionChainKey = '{}:{}'.format(symbol, token)
        try:
            # Convert Tick dataclass to dict for JSON serialization
            self.conn.set(optionChainKey, json.dumps(asdict(data), default=str))
        except Exception as e:
            raise Exception('Error - {}'.format(e))

    def get_option_chain(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Retrieve the current option chain for a symbol.
        """
        # Scan for keys matching the symbol pattern
        # Pattern: symbol:token
        pattern = f"{symbol}:*"
        keys = self.conn.keys(pattern)
        chain_data = []
        if keys:
            values = self.conn.mget(keys)
            for val in values:
                if val:
                    chain_data.append(json.loads(val))
        return chain_data
    
    def fetch_option_data(self, symbol: str, token: str) -> Dict[str, Any]:
        optionContractKey = '{}:{}'.format(symbol, token)
        try:
            data = self.conn.get(optionContractKey)
            if data:
                return json.loads(data)
            return {}
        except Exception as e:
            raise Exception('Error - {}'.format(e))

    def store_instruments(self, key: str, data: Any):
        self.conn.set(key, json.dumps(data, default=str))

    def get_instrument(self, token: str) -> Dict[str, Any]:
        try:
            data = self.conn.get(token)
            if data:
                return json.loads(data)
            raise Exception(f'Token {token} not found')
        except Exception as e:
            raise Exception('Error {}'.format(e))
