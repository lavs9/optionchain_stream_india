# Broker classes are NOT imported here.
# Each broker depends on a different optional SDK (kiteconnect, upstox-python-sdk,
# dhanhq, fyers-apiv3) that may not be installed in every deployment.
# Import only the broker you actually use:
#
#   from optionchain_stream.brokers.upstox_analytics_broker import UpstoxAnalyticsBroker
#   from optionchain_stream.brokers.upstox_broker import UpstoxBroker
#   from optionchain_stream.brokers.zerodha_broker import ZerodhaBroker
#   from optionchain_stream.brokers.fyers_broker import FyersBroker
#   from optionchain_stream.brokers.dhan_broker import DhanBroker
#
# BrokerCoordinator.from_config() already does lazy per-branch imports internally.
