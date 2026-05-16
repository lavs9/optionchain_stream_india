import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from optionchain_stream.formatters.wide import to_wide_rows
from optionchain_stream.analytics.pcr import compute_oi_zones
from optionchain_stream.analytics.gex import compute_gex_flip
from optionchain_stream.models import OptionChainRow


def _chain(strikes_oi, spot=25000.0, gamma=0.002):
    """Build a minimal chain dict. strikes_oi: list of (strike, ce_oi, pe_oi)."""
    return {
        "spot_price": spot,
        "strikes": [
            {
                "strike_price": s,
                "call_options": {
                    "symbol": f"NIFTY{s}CE", "ltp": 200.0, "bid": 199.0, "ask": 201.0,
                    "open": 0, "high": 0, "low": 0, "prev_close": 0,
                    "volume": 1000, "oi": ce_oi,
                    "option_greeks": {"iv": 0.18, "delta": 0.5, "theta": -10.0, "gamma": gamma, "vega": 5.0},
                },
                "put_options": {
                    "symbol": f"NIFTY{s}PE", "ltp": 150.0, "bid": 149.0, "ask": 151.0,
                    "open": 0, "high": 0, "low": 0, "prev_close": 0,
                    "volume": 800, "oi": pe_oi,
                    "option_greeks": {"iv": 0.20, "delta": -0.5, "theta": -9.0, "gamma": gamma, "vega": 4.5},
                },
            }
            for s, ce_oi, pe_oi in strikes_oi
        ],
    }


# ── tianjin-6r0: per-strike PCR ──────────────────────────────────────────────

def test_strike_pcr_formula():
    rows = to_wide_rows(_chain([(25000, 4000, 8000)]), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].strike_pcr == 8000 / 4000


def test_strike_pcr_zero_ce_oi_is_none():
    rows = to_wide_rows(_chain([(25000, 0, 5000)]), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].strike_pcr is None


# ── tianjin-6r0: OI zones ─────────────────────────────────────────────────────

def test_oi_zones_top3_resistance():
    strikes_oi = [
        (24500, 10000, 2000),
        (25000, 80000, 5000),  # highest CE OI → resistance
        (25500, 60000, 3000),
        (26000, 50000, 1000),
        (26500, 20000, 500),
    ]
    rows = to_wide_rows(_chain(strikes_oi), "NIFTY", "29MAY26", 1716000000, 50)
    zones = compute_oi_zones(rows)
    assert zones["resistance_strikes"][0] == 25000.0  # top CE OI


def test_oi_zones_top3_support():
    strikes_oi = [
        (24500, 2000, 90000),  # highest PE OI → support
        (25000, 5000, 60000),
        (25500, 3000, 40000),
        (26000, 1000, 20000),
    ]
    rows = to_wide_rows(_chain(strikes_oi), "NIFTY", "29MAY26", 1716000000, 50)
    zones = compute_oi_zones(rows)
    assert zones["support_strikes"][0] == 24500.0


def test_oi_zones_chain_pcr():
    strikes_oi = [(25000, 10000, 20000)]
    rows = to_wide_rows(_chain(strikes_oi), "NIFTY", "29MAY26", 1716000000, 50)
    zones = compute_oi_zones(rows)
    assert abs(zones["chain_pcr"] - 2.0) < 1e-9


def test_oi_zones_empty():
    zones = compute_oi_zones([])
    assert zones["resistance_strikes"] == []
    assert zones["support_strikes"] == []
    assert zones["chain_pcr"] == 0.0


# ── tianjin-6to: GEX per strike ──────────────────────────────────────────────

def test_gex_net_sign_positive_zone():
    # pe_oi > ce_oi → net_gex > 0 → vol damping zone
    rows = to_wide_rows(_chain([(25000, 1000, 5000)], spot=25000.0), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].net_gex > 0


def test_gex_net_sign_negative_zone():
    # ce_oi > pe_oi → net_gex < 0 → vol amplification zone
    rows = to_wide_rows(_chain([(25000, 5000, 1000)], spot=25000.0), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].net_gex < 0


def test_gex_flip_strike_between_adjacent():
    # Low strikes: ce_oi >> pe_oi → net_gex < 0 (vol amplification)
    # High strike: pe_oi >> ce_oi → net_gex >> 0 (vol damping), enough to flip cumulative
    strikes_oi = [
        (24500, 9000, 1000),    # net_gex ≈ -20M
        (25000, 5000, 1000),    # net_gex ≈ -10M; cumulative ≈ -30M
        (25500, 1000, 20000),   # net_gex ≈ +47M; cumulative goes positive → flip here
    ]
    rows = to_wide_rows(_chain(strikes_oi, spot=25000.0), "NIFTY", "29MAY26", 1716000000, 50)
    flip = compute_gex_flip(rows, spot_price=25000.0)
    assert flip is not None
    assert flip == 25500.0


def test_gex_zero_when_greeks_missing():
    # Build a response without option_greeks → quality_flag=2 → GEX should be 0
    response = {
        "spot_price": 25000.0,
        "strikes": [{
            "strike_price": 25000,
            "call_options": {
                "symbol": "NIFTY25000CE", "ltp": 200.0, "bid": 199.0, "ask": 201.0,
                "open": 0, "high": 0, "low": 0, "prev_close": 0, "volume": 0, "oi": 5000,
                # no option_greeks key
            },
            "put_options": {
                "symbol": "NIFTY25000PE", "ltp": 150.0, "bid": 149.0, "ask": 151.0,
                "open": 0, "high": 0, "low": 0, "prev_close": 0, "volume": 0, "oi": 5000,
            },
        }],
    }
    rows = to_wide_rows(response, "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].quality_flag == 2
    assert rows[0].ce_gex == 0.0
    assert rows[0].pe_gex == 0.0
    assert rows[0].net_gex == 0.0


# ── tianjin-bjh: delta OI ────────────────────────────────────────────────────

def test_delta_oi_first_cycle_is_zero():
    rows = to_wide_rows(_chain([(25000, 5000, 4000)]), "NIFTY", "29MAY26", 1716000000, 50)
    assert rows[0].ce_oi_change == 0
    assert rows[0].pe_oi_change == 0


def test_delta_oi_second_cycle_shows_diff():
    first_rows = to_wide_rows(_chain([(25000, 5000, 4000)]), "NIFTY", "29MAY26", 1716000000, 50)
    prev_snapshot = {r.strike: r for r in first_rows}
    second_rows = to_wide_rows(_chain([(25000, 6500, 3000)]), "NIFTY", "29MAY26", 1716000060, 50,
                                prev_snapshot=prev_snapshot)
    assert second_rows[0].ce_oi_change == 1500   # buildup
    assert second_rows[0].pe_oi_change == -1000  # unwinding
