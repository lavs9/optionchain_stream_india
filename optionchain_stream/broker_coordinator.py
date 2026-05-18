import logging
import threading
from typing import List, Dict, Any, Callable, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
from optionchain_stream.broker_interface import Broker
from optionchain_stream.models import Tick
from optionchain_stream.option_chain import OptionChainPoller

@dataclass
class BrokerConfig:
    """Configuration for a single broker instance"""
    broker: Broker
    subscription_limit: int  # Max instruments this broker can handle
    name: str = ""  # Friendly name for logging
    current_subscriptions: int = field(default=0, init=False)
    is_connected: bool = field(default=False, init=False)
    
    def available_capacity(self) -> int:
        """Returns number of additional instruments this broker can handle"""
        return max(0, self.subscription_limit - self.current_subscriptions)


class BrokerCoordinator:
    """
    Coordinates multiple broker instances and option chain pollers.
    
    Features:
    - Distributes instruments across multiple brokers
    - Unified callback interface for all data sources
    - Integrates real-time streaming with periodic polling
    - Thread-safe operation
    - Basic health monitoring
    
    Example:
        coordinator = BrokerCoordinator()
        coordinator.add_broker(upstox_broker1, subscription_limit=2000, name="Upstox-1")
        coordinator.add_broker(upstox_broker2, subscription_limit=2000, name="Upstox-2")
        
        coordinator.subscribe(tokens[:3000], mode="full")  # Auto-distributed
        coordinator.on_tick(my_callback)
        coordinator.connect_all()
    """
    
    def __init__(self):
        self.brokers: List[BrokerConfig] = []
        self.pollers: List[OptionChainPoller] = []
        self.callbacks: List[Callable[[List[Tick]], None]] = []
        self.lock = threading.Lock()
        self.stats = {
            'total_ticks': 0,
            'total_subscriptions': 0,
            'started_at': None
        }
        
    def add_broker(self, broker: Broker, subscription_limit: int, name: str = ""):
        """
        Add a broker instance to the coordinator.
        
        Args:
            broker: Broker instance (Upstox, Dhan, Fyers, etc.)
            subscription_limit: Max instruments for this broker (e.g., 2000 for Upstox full mode)
            name: Friendly name for logging/debugging
        """
        if not name:
            name = f"{broker.__class__.__name__}-{len(self.brokers) + 1}"
            
        config = BrokerConfig(
            broker=broker,
            subscription_limit=subscription_limit,
            name=name
        )
        self.brokers.append(config)
        
        # Attach callback to broker
        broker.on_tick(self._handle_broker_tick)
        
        logging.info(f"Added broker: {name} (limit: {subscription_limit})")
        
    def subscribe(self, tokens: List[str], mode: str = "full") -> Dict[str, int]:
        """
        Subscribe to instruments, auto-distributing across brokers.
        
        Args:
            tokens: List of instrument tokens
            mode: Subscription mode (full, ticker, quote)
            
        Returns:
            Dict mapping broker name to number of instruments assigned
        """
        if not self.brokers:
            raise ValueError("No brokers registered. Use add_broker() first.")
        
        distribution = {}
        remaining_tokens = tokens.copy()
        
        # Simple distribution: fill each broker to capacity
        for config in self.brokers:
            if not remaining_tokens:
                break
                
            capacity = config.available_capacity()
            if capacity <= 0:
                continue
                
            # Take as many as this broker can handle
            to_subscribe = remaining_tokens[:capacity]
            remaining_tokens = remaining_tokens[capacity:]
            
            # Subscribe to broker
            config.broker.subscribe(to_subscribe, mode=mode)
            config.current_subscriptions += len(to_subscribe)
            distribution[config.name] = len(to_subscribe)
            
            logging.info(f"Subscribed {len(to_subscribe)} instruments to {config.name}")
        
        if remaining_tokens:
            logging.warning(f"Could not subscribe to {len(remaining_tokens)} instruments (capacity exceeded)")
        
        with self.lock:
            self.stats['total_subscriptions'] = sum(config.current_subscriptions for config in self.brokers)
            
        return distribution
    
    def add_option_chain_poller(
        self,
        broker: Broker,
        symbol: str,
        expiry: str,
        poll_interval_seconds: int = 5,
        name: str = ""
    ) -> OptionChainPoller:
        """
        Add an option chain poller that will feed into the same tick stream.
        
        Args:
            broker: Broker instance to use for polling
            symbol: Underlying symbol (NIFTY, BANKNIFTY)
            expiry: Expiry date (YYYY-MM-DD)
            poll_interval_seconds: How often to poll
            name: Friendly name
            
        Returns:
            OptionChainPoller instance (already started)
        """
        if not name:
            name = f"Poller-{symbol}-{len(self.pollers) + 1}"
        
        poller = OptionChainPoller(
            broker=broker,
            symbol=symbol,
            expiry=expiry,
            poll_interval_seconds=poll_interval_seconds
        )
        
        # Attach callback
        poller.on_data(lambda data: self._handle_poller_data(data, name))
        
        self.pollers.append(poller)
        
        logging.info(f"Added option chain poller: {name} (interval: {poll_interval_seconds}s)")
        
        return poller
    
    def on_tick(self, callback: Callable[[List[Tick]], None]):
        """
        Register a callback for all tick data (from all brokers and pollers).
        
        Args:
            callback: Function that receives list of Tick objects
        """
        self.callbacks.append(callback)
        
    def connect_all(self):
        """Connect all registered brokers and start all pollers."""
        if not self.brokers and not self.pollers:
            raise ValueError("No brokers or pollers registered")
        
        with self.lock:
            self.stats['started_at'] = datetime.now()
        
        # Connect brokers in separate threads
        threads = []
        for config in self.brokers:
            thread = threading.Thread(
                target=self._connect_broker,
                args=(config,),
                daemon=True,
                name=f"Broker-{config.name}"
            )
            thread.start()
            threads.append(thread)
            
        # Start pollers
        for poller in self.pollers:
            poller.start()
            
        logging.info(f"Started {len(self.brokers)} brokers and {len(self.pollers)} pollers")
        
    def _connect_broker(self, config: BrokerConfig):
        """Connect a single broker (runs in thread)"""
        try:
            logging.info(f"Connecting broker: {config.name}")
            config.broker.connect()
            config.is_connected = True
        except Exception as e:
            logging.error(f"Error connecting {config.name}: {e}")
            config.is_connected = False
    
    def _handle_broker_tick(self, ticks: List[Tick]):
        """Internal callback for broker ticks"""
        with self.lock:
            self.stats['total_ticks'] += len(ticks)
        
        # Forward to all registered callbacks
        for callback in self.callbacks:
            try:
                callback(ticks)
            except Exception as e:
                logging.error(f"Error in tick callback: {e}")
    
    def _handle_poller_data(self, data: Dict[str, Any], poller_name: str):
        """Internal callback for poller data"""
        # Convert option chain data to Tick objects if needed
        # For now, just log - full conversion depends on data structure
        logging.debug(f"Received option chain data from {poller_name}")
        
        # TODO: Convert option chain strikes to Tick format and call callbacks
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get coordinator statistics and health metrics.
        
        Returns:
            Dict with metrics:
            - total_subscriptions: Total instruments subscribed across all brokers
            - total_ticks: Total ticks received
            - brokers: List of broker stats
            - pollers: List of poller stats
            - uptime_seconds: Seconds since connect_all()
        """
        with self.lock:
            uptime = None
            if self.stats['started_at']:
                uptime = (datetime.now() - self.stats['started_at']).total_seconds()
            
            return {
                'total_subscriptions': self.stats['total_subscriptions'],
                'total_ticks': self.stats['total_ticks'],
                'uptime_seconds': uptime,
                'brokers': [
                    {
                        'name': config.name,
                        'connected': config.is_connected,
                        'subscriptions': config.current_subscriptions,
                        'limit': config.subscription_limit,
                        'capacity': config.available_capacity()
                    }
                    for config in self.brokers
                ],
                'pollers': [
                    {
                        'symbol': poller.symbol,
                        'expiry': poller.expiry,
                        'interval': poller.poll_interval_seconds,
                        'running': poller.is_running
                    }
                    for poller in self.pollers
                ]
            }
    
    def stop_all(self):
        """Stop all pollers and disconnect brokers."""
        for poller in self.pollers:
            poller.stop()

        # Note: Broker disconnection depends on broker implementation
        logging.info("Stopped all pollers")

    # ── Methods required by OptionChainPoller.poll_once() ────────────────────

    def fetch_chain(self, underlying: str, expiry: str) -> dict:
        """
        Fetch option chain from the primary (first) registered broker.
        Returns the broker-normalised nested dict consumed by to_wide_rows().
        """
        if not self.brokers:
            raise RuntimeError("No brokers registered in BrokerCoordinator")
        return self.brokers[0].broker.fetch_option_chain(underlying, expiry)

    def get_instrument_provider(self):
        """
        Return the InstrumentProvider of the primary broker.
        Exposes get_active_expiries() and get_lotsize() to OptionChainPoller.
        """
        if not self.brokers:
            raise RuntimeError("No brokers registered in BrokerCoordinator")
        return self.brokers[0].broker.get_instrument_provider()

    # ── Factory ──────────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, cfg: dict) -> "BrokerCoordinator":
        """
        Build a BrokerCoordinator from a flat config dict.

        Required keys:
          broker     — "zerodha" | "upstox" | "fyers" | "dhan"
          api_key    — broker API key / client ID
          api_secret — access token (pre-generated; pipeline uses this pattern)

        Optional keys:
          analytics_token    — Upstox long-lived Analytics Token (1-year, no OAuth).
                               When present and broker=="upstox", UpstoxAnalyticsBroker
                               is used instead of the OAuth UpstoxBroker.
                               Generate at: https://account.upstox.com/developer/apps#analytics
          subscription_limit — default 2000

        Upstox — two auth modes
        -----------------------
        OAuth (daily token, streaming + trading):
            {"broker": "upstox", "api_key": "<client_id>", "api_secret": "<access_token>"}

        Analytics Token (1-year, read-only, no OAuth flow):
            {"broker": "upstox", "analytics_token": "<token>"}
            api_key / api_secret are ignored when analytics_token is provided.
        """
        broker_name = (cfg.get("broker") or "").lower().strip()
        api_key = cfg.get("api_key", "")
        api_secret = cfg.get("api_secret", "")  # treated as access_token
        analytics_token = cfg.get("analytics_token", "")
        limit = int(cfg.get("subscription_limit", 2000))

        # Upstox: analytics token mode takes precedence over OAuth mode
        if broker_name == "upstox" and analytics_token:
            from optionchain_stream.brokers.upstox_analytics_broker import UpstoxAnalyticsBroker
            broker = UpstoxAnalyticsBroker(analytics_token=analytics_token)

        elif broker_name == "zerodha":
            from optionchain_stream.brokers.zerodha_broker import ZerodhaBroker
            broker = ZerodhaBroker(api_key=api_key, access_token=api_secret)

        elif broker_name == "upstox":
            from optionchain_stream.brokers.upstox_broker import UpstoxBroker
            # client_secret and redirect_uri only needed for OAuth code-flow;
            # pipeline uses a pre-generated access_token so they can be empty.
            broker = UpstoxBroker(
                client_id=api_key,
                client_secret=cfg.get("client_secret", ""),
                redirect_uri=cfg.get("redirect_uri", ""),
                access_token=api_secret,
            )

        elif broker_name == "fyers":
            from optionchain_stream.brokers.fyers_broker import FyersBroker
            broker = FyersBroker(client_id=api_key, access_token=api_secret)

        elif broker_name == "dhan":
            from optionchain_stream.brokers.dhan_broker import DhanBroker
            broker = DhanBroker(client_id=api_key, access_token=api_secret)

        else:
            raise ValueError(
                f"Unknown broker {broker_name!r}. "
                f"Valid values: zerodha, upstox, fyers, dhan"
            )

        coord = cls()
        coord.add_broker(broker, subscription_limit=limit)
        return coord
