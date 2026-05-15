import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optionchain_stream.formatters.wide import to_wide_rows
from optionchain_stream.models import OptionChainRow


def _clean_response(strike=24000.0, ce_ltp=425.0, pe_ltp=380.0, ce_iv=0.18, pe_iv=0.20):
    return {
        'spot_price': 24350.0,
        'strikes': [
            {
                'strike_price': strike,
                'call_options': {
                    'symbol': f'NIFTY29MAY26{int(strike)}CE',
                    'ltp': ce_ltp, 'bid': 424.5, 'ask': 425.5,
                    'open': 410.0, 'high': 430.0, 'low': 405.0, 'prev_close': 400.0,
                    'volume': 12500, 'oi': 85000,
                    'option_greeks': {
                        'iv': ce_iv, 'delta': 0.62, 'theta': -45.2, 'gamma': 0.003, 'vega': 28.1,
                    },
                },
                'put_options': {
                    'symbol': f'NIFTY29MAY26{int(strike)}PE',
                    'ltp': pe_ltp, 'bid': 379.5, 'ask': 380.5,
                    'open': 370.0, 'high': 390.0, 'low': 365.0, 'prev_close': 360.0,
                    'volume': 9000, 'oi': 70000,
                    'option_greeks': {
                        'iv': pe_iv, 'delta': -0.38, 'theta': -42.1, 'gamma': 0.003, 'vega': 26.5,
                    },
                },
            }
        ],
    }


# ── Behavior 2: clean response → flag=0, correct mapping ─────────────────────

def test_clean_response_returns_one_row_per_strike():
    rows = to_wide_rows(_clean_response(), underlying="NIFTY", expiry="29MAY26",
                        timestamp=1716000000, lotsize=50)
    assert len(rows) == 1
    assert isinstance(rows[0], OptionChainRow)


def test_clean_response_fields_mapped_correctly():
    rows = to_wide_rows(_clean_response(), underlying="NIFTY", expiry="29MAY26",
                        timestamp=1716000000, lotsize=50)
    row = rows[0]
    assert row.underlying == "NIFTY"
    assert row.expiry == "29MAY26"
    assert row.strike == 24000.0
    assert row.timestamp == 1716000000
    assert row.lotsize == 50
    assert row.ce_ltp == 425.0
    assert row.ce_bid == 424.5
    assert row.ce_ask == 425.5
    assert row.ce_open == 410.0
    assert row.ce_high == 430.0
    assert row.ce_low == 405.0
    assert row.ce_prev_close == 400.0
    assert row.ce_volume == 12500
    assert row.ce_oi == 85000
    assert row.ce_iv == 0.18
    assert row.ce_delta == 0.62
    assert row.pe_ltp == 380.0
    assert row.pe_iv == 0.20
    assert row.pe_delta == -0.38


def test_clean_response_quality_flag_is_zero():
    rows = to_wide_rows(_clean_response(), underlying="NIFTY", expiry="29MAY26",
                        timestamp=1716000000, lotsize=50)
    assert rows[0].quality_flag == 0


def test_multiple_strikes_returns_one_row_each():
    response = {
        'spot_price': 24350.0,
        'strikes': [
            {
                'strike_price': s,
                'call_options': {
                    'symbol': f'NIFTY29MAY26{s}CE',
                    'ltp': 100.0, 'bid': 99.5, 'ask': 100.5,
                    'open': 95.0, 'high': 105.0, 'low': 90.0, 'prev_close': 98.0,
                    'volume': 1000, 'oi': 5000,
                    'option_greeks': {'iv': 0.18, 'delta': 0.5, 'theta': -10.0, 'gamma': 0.001, 'vega': 5.0},
                },
                'put_options': {
                    'symbol': f'NIFTY29MAY26{s}PE',
                    'ltp': 200.0, 'bid': 199.5, 'ask': 200.5,
                    'open': 195.0, 'high': 205.0, 'low': 190.0, 'prev_close': 198.0,
                    'volume': 2000, 'oi': 8000,
                    'option_greeks': {'iv': 0.22, 'delta': -0.5, 'theta': -12.0, 'gamma': 0.001, 'vega': 6.0},
                },
            }
            for s in [23800, 24000, 24200]
        ],
    }
    rows = to_wide_rows(response, underlying="NIFTY", expiry="29MAY26",
                        timestamp=1716000000, lotsize=50)
    assert len(rows) == 3
    strikes = [r.strike for r in rows]
    assert 23800 in strikes and 24000 in strikes and 24200 in strikes


# ── Behavior 3: zero LTP → flag=1 ─────────────────────────────────────────────

def test_zero_ce_ltp_sets_flag_1():
    rows = to_wide_rows(_clean_response(ce_ltp=0.0), underlying="NIFTY", expiry="29MAY26",
                        timestamp=1716000000, lotsize=50)
    assert rows[0].quality_flag == 1


def test_zero_pe_ltp_sets_flag_1():
    rows = to_wide_rows(_clean_response(pe_ltp=0.0), underlying="NIFTY", expiry="29MAY26",
                        timestamp=1716000000, lotsize=50)
    assert rows[0].quality_flag == 1


# ── Behavior 4: missing/zero greeks → flag=2 ──────────────────────────────────

def test_missing_option_greeks_key_sets_flag_2():
    response = _clean_response()
    del response['strikes'][0]['call_options']['option_greeks']
    rows = to_wide_rows(response, underlying="NIFTY", expiry="29MAY26",
                        timestamp=1716000000, lotsize=50)
    assert rows[0].quality_flag == 2


def test_both_iv_zero_sets_flag_2():
    rows = to_wide_rows(_clean_response(ce_iv=0.0, pe_iv=0.0), underlying="NIFTY",
                        expiry="29MAY26", timestamp=1716000000, lotsize=50)
    assert rows[0].quality_flag == 2


def test_one_iv_zero_does_not_set_flag_2():
    # Only both sides zero triggers flag=2
    rows = to_wide_rows(_clean_response(ce_iv=0.0, pe_iv=0.18), underlying="NIFTY",
                        expiry="29MAY26", timestamp=1716000000, lotsize=50)
    assert rows[0].quality_flag == 0


# ── Behavior 5: stale row → flag=4 ────────────────────────────────────────────

def test_identical_to_prev_snapshot_sets_flag_4():
    rows_first = to_wide_rows(_clean_response(), underlying="NIFTY", expiry="29MAY26",
                              timestamp=1716000000, lotsize=50)
    prev_snapshot = {rows_first[0].strike: rows_first[0]}

    rows_second = to_wide_rows(_clean_response(), underlying="NIFTY", expiry="29MAY26",
                               timestamp=1716000060, lotsize=50, prev_snapshot=prev_snapshot)
    assert rows_second[0].quality_flag == 4


def test_changed_ltp_does_not_set_stale_flag():
    rows_first = to_wide_rows(_clean_response(ce_ltp=425.0), underlying="NIFTY",
                              expiry="29MAY26", timestamp=1716000000, lotsize=50)
    prev_snapshot = {rows_first[0].strike: rows_first[0]}

    rows_second = to_wide_rows(_clean_response(ce_ltp=430.0), underlying="NIFTY",
                               expiry="29MAY26", timestamp=1716000060, lotsize=50,
                               prev_snapshot=prev_snapshot)
    assert rows_second[0].quality_flag == 0


# ── Behavior 6: robustness ────────────────────────────────────────────────────

def test_empty_strikes_returns_empty_list():
    rows = to_wide_rows({'spot_price': 24350.0, 'strikes': []},
                        underlying="NIFTY", expiry="29MAY26",
                        timestamp=1716000000, lotsize=50)
    assert rows == []


def test_missing_strikes_key_returns_empty_list():
    rows = to_wide_rows({'spot_price': 24350.0},
                        underlying="NIFTY", expiry="29MAY26",
                        timestamp=1716000000, lotsize=50)
    assert rows == []


def test_malformed_strike_does_not_raise():
    response = {'strikes': [{'strike_price': 24000.0}]}  # missing call/put options
    rows = to_wide_rows(response, underlying="NIFTY", expiry="29MAY26",
                        timestamp=1716000000, lotsize=50)
    # Should not raise; returns whatever rows it can (may be empty or partial)
    assert isinstance(rows, list)
