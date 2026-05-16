import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from optionchain_stream.analytics.straddle import (
    compute_atm_straddle,
    compute_synthetic_futures,
    compute_synthetic_futures_spread,
)
from optionchain_stream.models import OptionChainRow


def _row(strike, ce_ltp, pe_ltp):
    return OptionChainRow(
        timestamp=0, underlying="NIFTY", expiry="29MAY26", strike=float(strike),
        ce_symbol="", pe_symbol="", lotsize=50, quality_flag=0,
        ce_ltp=ce_ltp, ce_bid=0, ce_ask=0, ce_open=0, ce_high=0, ce_low=0, ce_prev_close=0,
        ce_volume=0, ce_oi=0, ce_iv=0, ce_delta=0, ce_theta=0, ce_gamma=0, ce_vega=0,
        pe_ltp=pe_ltp, pe_bid=0, pe_ask=0, pe_open=0, pe_high=0, pe_low=0, pe_prev_close=0,
        pe_volume=0, pe_oi=0, pe_iv=0, pe_delta=0, pe_theta=0, pe_gamma=0, pe_vega=0,
    )


def test_atm_straddle_selects_atm_strike():
    rows = [_row(24900, 300, 250), _row(25000, 200, 180), _row(25100, 100, 150)]
    result = compute_atm_straddle(rows, spot=25000.0)
    assert result["atm_strike"] == 25000.0
    assert result["straddle_premium"] == 200 + 180


def test_atm_straddle_implied_move_pct():
    rows = [_row(25000, 250, 250)]
    result = compute_atm_straddle(rows, spot=25000.0)
    assert abs(result["implied_move_pct"] - (500 / 25000 * 100)) < 1e-9


def test_atm_straddle_empty_rows():
    assert compute_atm_straddle([], spot=25000.0) == {}


def test_atm_straddle_zero_spot():
    rows = [_row(25000, 200, 180)]
    assert compute_atm_straddle(rows, spot=0.0) == {}


def test_synthetic_futures_formula():
    rows = [_row(25000, 200, 150)]
    result = compute_synthetic_futures(rows)
    assert len(result) == 1
    assert result[0]["strike"] == 25000.0
    assert result[0]["synthetic_fut"] == 200 - 150 + 25000  # 25050


def test_synthetic_futures_spread_mean_deviation():
    # Two rows both with synthetic = spot → spread = 0
    spot = 25000.0
    rows = [_row(25000, 100, 100), _row(24900, 200, 200)]  # synth = 25000 and 24900
    result = compute_synthetic_futures_spread(rows, spot)
    # row1: |25000 - 25000| = 0; row2: |24900 - 25000| = 100; mean = 50
    assert abs(result - 50.0) < 1e-9
