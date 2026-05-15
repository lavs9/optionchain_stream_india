import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock, patch
from optionchain_stream.poller import OptionChainPoller
from optionchain_stream.models import OptionChainRow, CycleHealth


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_chain_response(strike=24000.0, ce_ltp=425.0, pe_ltp=380.0):
    return {
        'spot_price': 24350.0,
        'strikes': [{
            'strike_price': strike,
            'call_options': {
                'symbol': f'NIFTY29MAY26{int(strike)}CE',
                'ltp': ce_ltp, 'bid': 424.5, 'ask': 425.5,
                'open': 410.0, 'high': 430.0, 'low': 405.0, 'prev_close': 400.0,
                'volume': 12500, 'oi': 85000,
                'option_greeks': {'iv': 0.18, 'delta': 0.62, 'theta': -45.2, 'gamma': 0.003, 'vega': 28.1},
            },
            'put_options': {
                'symbol': f'NIFTY29MAY26{int(strike)}PE',
                'ltp': pe_ltp, 'bid': 379.5, 'ask': 380.5,
                'open': 370.0, 'high': 390.0, 'low': 365.0, 'prev_close': 360.0,
                'volume': 9000, 'oi': 70000,
                'option_greeks': {'iv': 0.20, 'delta': -0.38, 'theta': -42.1, 'gamma': 0.003, 'vega': 26.5},
            },
        }],
    }


def _make_coordinator(side_effect=None, expiries=None):
    """Returns a mock BrokerCoordinator."""
    coordinator = MagicMock()
    if side_effect:
        coordinator.fetch_chain.side_effect = side_effect
    else:
        coordinator.fetch_chain.return_value = _make_chain_response()

    instrument_provider = MagicMock()
    instrument_provider.get_active_expiries.return_value = expiries or ["29MAY26"]
    coordinator.get_instrument_provider.return_value = instrument_provider
    return coordinator


def _make_calendar(is_open=True):
    cal = MagicMock()
    cal.is_market_open.return_value = is_open
    return cal


# ── Behavior 7: is_market_open delegates to calendar ─────────────────────────

def test_is_market_open_delegates_to_calendar():
    poller = OptionChainPoller(
        broker_coordinator=_make_coordinator(),
        symbols=["NIFTY"],
        market_calendar=_make_calendar(is_open=True),
    )
    assert poller.is_market_open() is True


def test_is_market_closed_delegates_to_calendar():
    poller = OptionChainPoller(
        broker_coordinator=_make_coordinator(),
        symbols=["NIFTY"],
        market_calendar=_make_calendar(is_open=False),
    )
    assert poller.is_market_open() is False


# ── Behavior 8: poll_once returns correct shape ───────────────────────────────

def test_poll_once_returns_tuple_of_rows_and_health():
    poller = OptionChainPoller(
        broker_coordinator=_make_coordinator(),
        symbols=["NIFTY"],
        market_calendar=_make_calendar(),
    )
    result = poller.poll_once()
    assert isinstance(result, tuple)
    rows, health = result
    assert isinstance(rows, list)
    assert isinstance(health, CycleHealth)


def test_poll_once_rows_are_option_chain_rows():
    poller = OptionChainPoller(
        broker_coordinator=_make_coordinator(),
        symbols=["NIFTY"],
        market_calendar=_make_calendar(),
    )
    rows, _ = poller.poll_once()
    assert all(isinstance(r, OptionChainRow) for r in rows)


def test_poll_once_health_cycle_type():
    poller = OptionChainPoller(
        broker_coordinator=_make_coordinator(),
        symbols=["NIFTY"],
        market_calendar=_make_calendar(),
    )
    _, health = poller.poll_once()
    assert health.cycle_type == "option_live"


def test_poll_once_health_symbols_expected_matches_symbols_list():
    poller = OptionChainPoller(
        broker_coordinator=_make_coordinator(),
        symbols=["NIFTY", "BANKNIFTY"],
        market_calendar=_make_calendar(),
    )
    _, health = poller.poll_once()
    assert health.symbols_expected == 2


def test_poll_once_health_symbols_received_on_success():
    poller = OptionChainPoller(
        broker_coordinator=_make_coordinator(),
        symbols=["NIFTY"],
        market_calendar=_make_calendar(),
    )
    _, health = poller.poll_once()
    assert health.symbols_received == 1


def test_poll_once_health_has_duration_ms():
    poller = OptionChainPoller(
        broker_coordinator=_make_coordinator(),
        symbols=["NIFTY"],
        market_calendar=_make_calendar(),
    )
    _, health = poller.poll_once()
    assert isinstance(health.duration_ms, int)
    assert health.duration_ms >= 0


# ── Behavior 9: broker failure → cycle continues, gaps counted ────────────────

def test_poll_once_broker_failure_does_not_raise():
    coordinator = _make_coordinator(side_effect=RuntimeError("API down"))
    poller = OptionChainPoller(
        broker_coordinator=coordinator,
        symbols=["NIFTY"],
        market_calendar=_make_calendar(),
    )
    rows, health = poller.poll_once()  # must not raise
    assert isinstance(rows, list)
    assert isinstance(health, CycleHealth)


def test_poll_once_partial_failure_counts_gaps():
    def side_effect(underlying, expiry):
        if underlying == "BANKNIFTY":
            raise RuntimeError("timeout")
        return _make_chain_response()

    coordinator = _make_coordinator(side_effect=side_effect)
    poller = OptionChainPoller(
        broker_coordinator=coordinator,
        symbols=["NIFTY", "BANKNIFTY"],
        market_calendar=_make_calendar(),
    )
    rows, health = poller.poll_once()
    assert health.symbols_received == 1
    assert health.symbols_expected == 2
    assert health.gaps >= 1


def test_poll_once_all_failures_error_field_set():
    coordinator = _make_coordinator(side_effect=RuntimeError("API down"))
    poller = OptionChainPoller(
        broker_coordinator=coordinator,
        symbols=["NIFTY"],
        market_calendar=_make_calendar(),
    )
    _, health = poller.poll_once()
    assert health.error is not None
