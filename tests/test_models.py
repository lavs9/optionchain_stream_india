import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.models import OptionChainRow, CycleHealth


def _make_row(**overrides):
    defaults = dict(
        timestamp=1716000000, underlying="NIFTY", expiry="29MAY26", strike=24000.0,
        ce_symbol="NIFTY29MAY2624000CE", ce_ltp=425.0, ce_bid=424.5, ce_ask=425.5,
        ce_open=410.0, ce_high=430.0, ce_low=405.0, ce_prev_close=400.0,
        ce_volume=12500, ce_oi=85000,
        ce_iv=0.18, ce_delta=0.62, ce_theta=-45.2, ce_gamma=0.003, ce_vega=28.1,
        pe_symbol="NIFTY29MAY2624000PE", pe_ltp=380.0, pe_bid=379.5, pe_ask=380.5,
        pe_open=370.0, pe_high=390.0, pe_low=365.0, pe_prev_close=360.0,
        pe_volume=9000, pe_oi=70000,
        pe_iv=0.20, pe_delta=-0.38, pe_theta=-42.1, pe_gamma=0.003, pe_vega=26.5,
        lotsize=50, quality_flag=0,
    )
    defaults.update(overrides)
    return OptionChainRow(**defaults)


def test_option_chain_row_instantiates():
    row = _make_row()
    assert row.underlying == "NIFTY"
    assert row.strike == 24000.0
    assert row.ce_ltp == 425.0
    assert row.pe_ltp == 380.0
    assert row.quality_flag == 0
    assert row.lotsize == 50


def test_cycle_health_instantiates():
    health = CycleHealth(
        ts=1716000000,
        cycle_type="option_live",
        symbols_expected=5,
        symbols_received=5,
        gaps=0,
        stale_warnings=0,
        duration_ms=1200,
        error=None,
    )
    assert health.cycle_type == "option_live"
    assert health.symbols_received == 5
    assert health.error is None


def test_cycle_health_with_error():
    health = CycleHealth(
        ts=1716000000, cycle_type="option_live",
        symbols_expected=5, symbols_received=3,
        gaps=2, stale_warnings=0, duration_ms=800,
        error="Connection timeout",
    )
    assert health.error == "Connection timeout"
    assert health.gaps == 2
