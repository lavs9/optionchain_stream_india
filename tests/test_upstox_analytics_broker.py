import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import patch, MagicMock
from optionchain_stream.brokers.upstox_analytics_broker import (
    UpstoxAnalyticsBroker,
    _normalize_chain,
    _INSTRUMENT_KEY_MAP,
)
from optionchain_stream.broker_coordinator import BrokerCoordinator
import pytest


# ── _normalize_chain unit tests ───────────────────────────────────────────────

_SAMPLE_RAW = {
    "status": "success",
    "data": [
        {
            "expiry": "2026-05-29",
            "strike_price": 24000,
            "underlying_key": "NSE_INDEX|Nifty 50",
            "underlying_spot_price": 24500.0,
            "call_options": {
                "instrument_key": "NSE_FO|11111",
                "market_data": {
                    "ltp": 650.0, "volume": 5000, "oi": 80000,
                    "close_price": 640.0, "bid_price": 649.0, "ask_price": 651.0,
                },
                "option_greeks": {"iv": 0.18, "delta": 0.62, "gamma": 0.003, "theta": -45.0, "vega": 28.0, "pop": 0.4},
            },
            "put_options": {
                "instrument_key": "NSE_FO|11112",
                "market_data": {
                    "ltp": 200.0, "volume": 3000, "oi": 60000,
                    "close_price": 195.0, "bid_price": 199.0, "ask_price": 201.0,
                },
                "option_greeks": {"iv": 0.20, "delta": -0.38, "gamma": 0.003, "theta": -42.0, "vega": 26.0, "pop": 0.6},
            },
        }
    ],
}


def test_normalize_spot_price():
    result = _normalize_chain(_SAMPLE_RAW)
    assert result["spot_price"] == 24500.0


def test_normalize_strike_count():
    result = _normalize_chain(_SAMPLE_RAW)
    assert len(result["strikes"]) == 1


def test_normalize_strike_price():
    result = _normalize_chain(_SAMPLE_RAW)
    assert result["strikes"][0]["strike_price"] == 24000.0


def test_normalize_ce_fields():
    result = _normalize_chain(_SAMPLE_RAW)
    ce = result["strikes"][0]["call_options"]
    assert ce["ltp"] == 650.0
    assert ce["bid"] == 649.0
    assert ce["ask"] == 651.0
    assert ce["prev_close"] == 640.0
    assert ce["volume"] == 5000
    assert ce["oi"] == 80000
    assert ce["symbol"] == "NSE_FO|11111"


def test_normalize_pe_greeks():
    result = _normalize_chain(_SAMPLE_RAW)
    g = result["strikes"][0]["put_options"]["option_greeks"]
    assert g["iv"] == 0.20
    assert g["delta"] == -0.38
    assert g["gamma"] == 0.003
    assert g["theta"] == -42.0
    assert g["vega"] == 26.0


def test_normalize_ohlc_defaults_to_zero():
    result = _normalize_chain(_SAMPLE_RAW)
    ce = result["strikes"][0]["call_options"]
    assert ce["open"] == 0.0
    assert ce["high"] == 0.0
    assert ce["low"] == 0.0


def test_normalize_empty_data():
    result = _normalize_chain({"status": "success", "data": []})
    assert result == {"spot_price": 0.0, "strikes": []}


def test_normalize_missing_data_key():
    result = _normalize_chain({})
    assert result == {"spot_price": 0.0, "strikes": []}


# ── Instrument key mapping ────────────────────────────────────────────────────

def test_instrument_key_map_nifty():
    assert _INSTRUMENT_KEY_MAP["NIFTY"] == "NSE_INDEX|Nifty 50"


def test_instrument_key_map_banknifty():
    assert _INSTRUMENT_KEY_MAP["BANKNIFTY"] == "NSE_INDEX|Nifty Bank"


# ── UpstoxAnalyticsBroker: fetch_option_chain ─────────────────────────────────

def test_fetch_option_chain_uses_correct_endpoint():
    broker = UpstoxAnalyticsBroker(analytics_token="test-token")
    mock_resp = MagicMock()
    mock_resp.json.return_value = _SAMPLE_RAW
    mock_resp.raise_for_status.return_value = None

    with patch.object(broker._session, "get", return_value=mock_resp) as mock_get:
        result = broker.fetch_option_chain("NIFTY", "2026-05-29")

    mock_get.assert_called_once_with(
        "https://api.upstox.com/v2/option/chain",
        params={"instrument_key": "NSE_INDEX|Nifty 50", "expiry_date": "2026-05-29"},
        timeout=10,
    )
    assert result["spot_price"] == 24500.0


def test_fetch_option_chain_unknown_symbol_passes_as_is():
    broker = UpstoxAnalyticsBroker(analytics_token="test-token")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status.return_value = None

    with patch.object(broker._session, "get", return_value=mock_resp) as mock_get:
        broker.fetch_option_chain("MIDCPNIFTY", "2026-05-29")

    call_params = mock_get.call_args[1]["params"]
    assert call_params["instrument_key"] == "NSE_INDEX|Nifty Mid Select"


def test_fetch_option_chain_http_error_returns_empty():
    import requests
    broker = UpstoxAnalyticsBroker(analytics_token="test-token")
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("403")

    with patch.object(broker._session, "get", return_value=mock_resp):
        result = broker.fetch_option_chain("NIFTY", "2026-05-29")

    assert result == {"spot_price": 0.0, "strikes": []}


def test_auth_header_set_on_session():
    broker = UpstoxAnalyticsBroker(analytics_token="my-secret-token")
    assert broker._session.headers["Authorization"] == "Bearer my-secret-token"


# ── Unsupported streaming methods raise ───────────────────────────────────────

def test_subscribe_raises():
    broker = UpstoxAnalyticsBroker(analytics_token="t")
    with pytest.raises(NotImplementedError):
        broker.subscribe(["token1"])


def test_on_tick_raises():
    broker = UpstoxAnalyticsBroker(analytics_token="t")
    with pytest.raises(NotImplementedError):
        broker.on_tick(lambda ticks: None)


def test_connect_raises():
    broker = UpstoxAnalyticsBroker(analytics_token="t")
    with pytest.raises(NotImplementedError):
        broker.connect()


def test_authenticate_is_noop():
    broker = UpstoxAnalyticsBroker(analytics_token="t")
    broker.authenticate()  # should not raise


# ── BrokerCoordinator.from_config routing ─────────────────────────────────────

def test_from_config_upstox_with_analytics_token_uses_analytics_broker():
    coord = BrokerCoordinator.from_config({
        "broker": "upstox",
        "analytics_token": "eyJ_test_token",
    })
    assert len(coord.brokers) == 1
    assert isinstance(coord.brokers[0].broker, UpstoxAnalyticsBroker)


def test_from_config_upstox_without_analytics_token_uses_oauth_broker():
    from optionchain_stream.brokers.upstox_broker import UpstoxBroker
    coord = BrokerCoordinator.from_config({
        "broker": "upstox",
        "api_key": "client_id",
        "api_secret": "access_token",
    })
    assert isinstance(coord.brokers[0].broker, UpstoxBroker)
