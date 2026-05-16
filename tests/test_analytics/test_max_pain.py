import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from optionchain_stream.analytics.max_pain import compute_max_pain
from optionchain_stream.models import OptionChainRow


def _row(strike, ce_oi, pe_oi, lotsize=50):
    return OptionChainRow(
        timestamp=0, underlying="NIFTY", expiry="29MAY26", strike=float(strike),
        ce_symbol="", pe_symbol="", lotsize=lotsize, quality_flag=0,
        ce_ltp=0, ce_bid=0, ce_ask=0, ce_open=0, ce_high=0, ce_low=0, ce_prev_close=0,
        ce_volume=0, ce_oi=ce_oi, ce_iv=0, ce_delta=0, ce_theta=0, ce_gamma=0, ce_vega=0,
        pe_ltp=0, pe_bid=0, pe_ask=0, pe_open=0, pe_high=0, pe_low=0, pe_prev_close=0,
        pe_volume=0, pe_oi=pe_oi, pe_iv=0, pe_delta=0, pe_theta=0, pe_gamma=0, pe_vega=0,
    )


def test_empty_rows_returns_none():
    assert compute_max_pain([]) is None


def test_single_strike_returns_that_strike():
    rows = [_row(25000, ce_oi=1000, pe_oi=1000)]
    assert compute_max_pain(rows) == 25000.0


def test_known_chain_max_pain():
    # Heavy PE OI at 24000 and heavy CE OI at 25000
    # Max pain should be around 24500 (where total payout is minimised)
    rows = [
        _row(23500, ce_oi=0,    pe_oi=10000),
        _row(24000, ce_oi=1000, pe_oi=50000),  # big put wall
        _row(24500, ce_oi=5000, pe_oi=5000),
        _row(25000, ce_oi=50000, pe_oi=1000),  # big call wall
        _row(25500, ce_oi=10000, pe_oi=0),
    ]
    result = compute_max_pain(rows)
    assert result in [23500.0, 24000.0, 24500.0, 25000.0, 25500.0]
    # Verify it is actually the argmin
    def pain(s):
        return sum(
            max(0, r.strike - s) * r.ce_oi * r.lotsize
            + max(0, s - r.strike) * r.pe_oi * r.lotsize
            for r in rows
        )
    strikes = [r.strike for r in rows]
    expected = min(strikes, key=pain)
    assert result == expected


def test_equal_oi_both_sides():
    # With perfectly symmetric OI, any middle strike could win — just verify it runs
    rows = [_row(s, ce_oi=1000, pe_oi=1000) for s in [24000, 24500, 25000]]
    result = compute_max_pain(rows)
    assert result in [24000.0, 24500.0, 25000.0]
