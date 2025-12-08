"""
Instrument Cache Manager

Provides Redis-based caching for instrument data with in-memory fallback.
"""

import json
import pickle
from typing import List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class InstrumentCache:
    """
    Caching layer for instrument data.
    Uses Redis if available, falls back to in-memory cache.
    """
    
    def __init__(self, cache_ttl_seconds: int = 3600, redis_host: str = 'localhost', redis_port: int = 6379):
        """
        Initialize cache manager.
        
        Args:
            cache_ttl_seconds: Time-to-live for cache (default: 1 hour)
            redis_host: Redis host (default: localhost)
            redis_port: Redis port (default: 6379)
        """
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._use_redis = False
        self._redis_client = None
        
        # In-memory fallback
        self._memory_cache = {}
        self._memory_timestamps = {}
        
        # Try to connect to Redis
        try:
            import redis
            self._redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            # Test connection
            self._redis_client.ping()
            self._use_redis = True
            logger.info(f"✅ Connected to Redis at {redis_host}:{redis_port}")
        except Exception as e:
            logger.warning(f"⚠️  Redis not available ({e}), using in-memory cache")
            self._use_redis = False
    
    def get(self, key: str) -> Optional[List]:
        """Get instruments from cache"""
        if self._use_redis:
            try:
                data = self._redis_client.get(f"instruments:{key}")
                if data:
                    logger.debug(f"✅ Cache hit (Redis): {key}")
                    return pickle.loads(data)
                logger.debug(f"❌ Cache miss (Redis): {key}")
                return None
            except Exception as e:
                logger.warning(f"Redis get error: {e}, falling back to memory")
                self._use_redis = False
        
        # In-memory fallback
        if key in self._memory_cache:
            age = datetime.now() - self._memory_timestamps[key]
            if age < self.cache_ttl:
                logger.debug(f"✅ Cache hit (memory): {key}")
                return self._memory_cache[key]
            else:
                logger.debug(f"⏰ Cache expired (memory): {key}")
                del self._memory_cache[key]
                del self._memory_timestamps[key]
        
        logger.debug(f"❌ Cache miss (memory): {key}")
        return None
    
    def set(self, key: str, instruments: List):
        """Store instruments in cache"""
        if self._use_redis:
            try:
                serialized = pickle.dumps(instruments)
                self._redis_client.setex(
                    f"instruments:{key}",
                    int(self.cache_ttl.total_seconds()),
                    serialized
                )
                logger.info(f"💾 Cached to Redis: {key} ({len(instruments)} items, TTL: {self.cache_ttl.total_seconds()}s)")
                return
            except Exception as e:
                logger.warning(f"Redis set error: {e}, falling back to memory")
                self._use_redis = False
        
        # In-memory fallback
        self._memory_cache[key] = instruments
        self._memory_timestamps[key] = datetime.now()
        logger.info(f"💾 Cached to memory: {key} ({len(instruments)} items)")
    
    def clear(self, key: Optional[str] = None):
        """Clear cache for specific key or all keys"""
        if key:
            if self._use_redis:
                try:
                    self._redis_client.delete(f"instruments:{key}")
                except:
                    pass
            if key in self._memory_cache:
                del self._memory_cache[key]
                del self._memory_timestamps[key]
            logger.info(f"🗑️  Cleared cache: {key}")
        else:
            if self._use_redis:
                try:
                    pattern = "instruments:*"
                    keys = self._redis_client.keys(pattern)
                    if keys:
                        self._redis_client.delete(*keys)
                except:
                    pass
            self._memory_cache.clear()
            self._memory_timestamps.clear()
            logger.info("🗑️  Cleared all caches")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        return {
            'backend': 'redis' if self._use_redis else 'memory',
            'ttl_seconds': self.cache_ttl.total_seconds(),
            'memory_keys': len(self._memory_cache),
            'redis_connected': self._use_redis
        }
