import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from optionchain_stream.formatters.wide import to_wide_rows
from optionchain_stream.analytics.atm import get_atm_strike


def _make_response(strikes, spot=25000.0, expiry="29MAY26"):
    """Build a minimal chain response for testing."""
    return {
        "spot_price": spot,
        "strikes": [
            {
                "strike_price": s,
                "call_options": {
                    "symbol": f"NIFTY{s}CE", "ltp": 200.0, "bid": 199.0, "ask": 201.0,
                    "open": 195.0, "high": 210.0, "low": 190.0, "prev_close": 198.0,
                    "volume": 1000, "oi": 5000,
                    "option_greeks": {"iv": 0.18, "delta": 0.5, "theta": -10.0, "gamma": 0.002, "vega": 5.0},
                },
                "put_options": {
                    "symbol": f"NIFTY{s}PE", "ltp": 150.0, "bid": 149.0, "ask": 151.0,
                    "open": 145.0, "high": 160.0, "low": 140.0, "prev_close": 148.0,
                    "volume": 800, "oi": 4000,
                    "option_greeks": {"iv": 0.20, "delta": -0.5, "theta": -9.0, "gamma": 0.002, "vega": 4.5},
                },
            }
            for s in strikes
        ],
    }


# tianjin-7nm: moneyness classification

def test_strike_below_spot_is_itm():
    rows = to_wide_rows(_make_response([24900], spot=25000.0), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].moneyness == "ITM"


def test_strike_above_spot_is_otm():
    rows = to_wide_rows(_make_response([25100], spot=25000.0), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].moneyness == "OTM"


def test_strike_within_02pct_is_atm():
    # 25000 * 0.002 = 50 → anything within 50 pts of 25000 is ATM
    rows = to_wide_rows(_make_response([25000], spot=25000.0), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].moneyness == "ATM"


def test_strike_at_spot_exact_is_atm():
    rows = to_wide_rows(_make_response([24500], spot=24500.0), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].moneyness == "ATM"


# tianjin-7nm: intrinsic and time value

def test_itm_ce_intrinsic():
    # strike=24900, spot=25000 → ce_intrinsic = 25000 - 24900 = 100
    rows = to_wide_rows(_make_response([24900], spot=25000.0), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].ce_intrinsic == 100.0


def test_otm_ce_intrinsic_is_zero():
    # strike=25100, spot=25000 → ce_intrinsic = max(0, 25000-25100) = 0
    rows = to_wide_rows(_make_response([25100], spot=25000.0), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].ce_intrinsic == 0.0


def test_otm_ce_time_value_equals_ce_ltp():
    # OTM call: time value = ltp (no intrinsic)
    rows = to_wide_rows(_make_response([25100], spot=25000.0), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].ce_time_value == rows[0].ce_ltp


def test_itm_ce_time_value():
    # ce_ltp=200, ce_intrinsic=100 → ce_time_value=100
    rows = to_wide_rows(_make_response([24900], spot=25000.0), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].ce_time_value == 200.0 - 100.0


def test_pe_intrinsic_itm_put():
    # strike=25100, spot=25000 → pe_intrinsic = max(0, 25100-25000) = 100
    rows = to_wide_rows(_make_response([25100], spot=25000.0), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].pe_intrinsic == 100.0


# tianjin-7nm: DTE

def test_dte_computed_correctly():
    # Use a fixed timestamp and expiry to verify arithmetic
    import datetime
    expiry = "29MAY26"
    # 2026-05-16 → 2026-05-29 = 13 days
    ts = int(datetime.datetime(2026, 5, 16, 10, 0, 0).timestamp())
    rows = to_wide_rows(_make_response([25000], spot=25000.0, expiry=expiry), "NIFTY", expiry, ts, 50)
    assert rows[0].days_to_expiry == 13


# tianjin-7nm: get_atm_strike

def test_get_atm_strike_returns_closest():
    response = _make_response([24900, 25000, 25200], spot=25000.0)
    rows = to_wide_rows(response, "NIFTY", "29MAY26", 1716000000, 50)
    atm = get_atm_strike(rows, 25150.0)
    assert atm is not None
    assert atm.strike == 25200.0  # 50 pts closer than 25000 (200 pts away)


def test_get_atm_strike_empty_returns_none():
    from optionchain_stream.analytics.atm import get_atm_strike
    assert get_atm_strike([], 25000.0) is None
