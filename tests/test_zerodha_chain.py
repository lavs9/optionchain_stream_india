"""
Tests for ZerodhaChainFetcher.

Unit tests use mocked kite client + in-memory fixture instrument CSV.
Integration test hits live Zerodha API (requires real credentials via env vars).
"""
import sys, os, csv, io, datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import MagicMock, patch

from optionchain_stream.brokers.zerodha_chain import ZerodhaChainFetcher


# ── Fixture helpers ────────────────────────────────────────────────────────────

def _make_instrument_csv(rows: list[dict]) -> str:
    fields = [
        'instrument_token', 'exchange_token', 'tradingsymbol', 'name',
        'last_price', 'expiry', 'strike', 'tick_size', 'lot_size',
        'instrument_type', 'segment', 'exchange',
    ]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    for r in rows:
        row = {f: r.get(f, '') for f in fields}
        w.writerow(row)
    return buf.getvalue()


def _nifty_row(strike, itype, token=None):
    token = token or str(9990000 + int(strike) + (0 if itype == "CE" else 1))
    sym = f"NIFTY2651{int(strike)}{itype}"
    return {
        'instrument_token': token, 'exchange_token': str(int(token) >> 8),
        'tradingsymbol': sym, 'name': 'NIFTY', 'last_price': '0',
        'expiry': '2026-05-19', 'strike': str(strike), 'tick_size': '0.05',
        'lot_size': '65', 'instrument_type': itype, 'segment': 'NFO-OPT',
        'exchange': 'NFO',
    }


def _make_kite(spot=23800.0, ce_ltp=225.0, pe_ltp=130.0):
    kite = MagicMock()

    def quote(symbols):
        result = {}
        for sym in symbols:
            ts = sym.replace('NFO:', '')
            if ts.endswith('CE'):
                ltp = ce_ltp
                ohlc = {'open': 200.0, 'high': 260.0, 'low': 165.0, 'close': 172.0}
            elif ts.endswith('PE'):
                ltp = pe_ltp
                ohlc = {'open': 155.0, 'high': 186.0, 'low': 112.0, 'close': 176.0}
            else:
                # spot quote
                ltp = spot
                ohlc = {}

            result[sym] = {
                'last_price': ltp,
                'volume': 1000000,
                'oi': 5000000,
                'ohlc': ohlc,
                'depth': {
                    'buy': [{'price': ltp - 0.5, 'quantity': 65, 'orders': 1}],
                    'sell': [{'price': ltp + 0.5, 'quantity': 65, 'orders': 1}],
                },
            }
        return result

    kite.quote.side_effect = quote
    return kite


def _make_fetcher(strikes=None, kite=None):
    strikes = strikes or [23700.0, 23800.0]
    csv_content = _make_instrument_csv(
        [_nifty_row(s, t) for s in strikes for t in ('CE', 'PE')]
    )
    kite = kite or _make_kite()
    fetcher = ZerodhaChainFetcher(kite_client=kite, instrument_cache_dir="/tmp")
    fetcher._instrument_csv = csv_content  # inject fixture without HTTP
    return fetcher


# ── Behavior: output shape matches Upstox broker contract ─────────────────────

def test_fetch_chain_returns_dict_with_spot_price():
    fetcher = _make_fetcher()
    result = fetcher.fetch_chain("NIFTY", "2026-05-19")
    assert "spot_price" in result
    assert isinstance(result["spot_price"], float)


def test_fetch_chain_returns_strikes_list():
    fetcher = _make_fetcher()
    result = fetcher.fetch_chain("NIFTY", "2026-05-19")
    assert "strikes" in result
    assert isinstance(result["strikes"], list)


def test_fetch_chain_one_entry_per_strike():
    fetcher = _make_fetcher(strikes=[23700.0, 23800.0])
    result = fetcher.fetch_chain("NIFTY", "2026-05-19")
    assert len(result["strikes"]) == 2


def test_fetch_chain_strike_has_call_and_put():
    fetcher = _make_fetcher()
    result = fetcher.fetch_chain("NIFTY", "2026-05-19")
    strike = result["strikes"][0]
    assert "strike_price" in strike
    assert "call_options" in strike
    assert "put_options" in strike


def test_fetch_chain_call_options_has_required_fields():
    fetcher = _make_fetcher()
    result = fetcher.fetch_chain("NIFTY", "2026-05-19")
    ce = result["strikes"][0]["call_options"]
    for field in ("symbol", "ltp", "bid", "ask", "open", "high", "low",
                  "prev_close", "volume", "oi", "option_greeks"):
        assert field in ce, f"missing field: {field}"


def test_fetch_chain_option_greeks_has_all_keys():
    fetcher = _make_fetcher()
    result = fetcher.fetch_chain("NIFTY", "2026-05-19")
    greeks = result["strikes"][0]["call_options"]["option_greeks"]
    for key in ("iv", "delta", "theta", "gamma", "vega"):
        assert key in greeks, f"missing greek: {key}"


def test_fetch_chain_greeks_are_floats():
    fetcher = _make_fetcher()
    result = fetcher.fetch_chain("NIFTY", "2026-05-19")
    greeks = result["strikes"][0]["call_options"]["option_greeks"]
    for key, val in greeks.items():
        assert isinstance(val, float), f"{key} should be float, got {type(val)}"


def test_fetch_chain_ltp_matches_quote_response():
    fetcher = _make_fetcher(kite=_make_kite(ce_ltp=225.0))
    result = fetcher.fetch_chain("NIFTY", "2026-05-19")
    ce_ltp = result["strikes"][0]["call_options"]["ltp"]
    assert ce_ltp == pytest.approx(225.0)


def test_fetch_chain_bid_ask_from_depth():
    fetcher = _make_fetcher(kite=_make_kite(ce_ltp=225.0))
    result = fetcher.fetch_chain("NIFTY", "2026-05-19")
    ce = result["strikes"][0]["call_options"]
    assert ce["bid"] == pytest.approx(224.5)
    assert ce["ask"] == pytest.approx(225.5)


def test_fetch_chain_ohlc_mapped():
    fetcher = _make_fetcher()
    result = fetcher.fetch_chain("NIFTY", "2026-05-19")
    ce = result["strikes"][0]["call_options"]
    assert ce["open"] == 200.0
    assert ce["prev_close"] == 172.0


def test_fetch_chain_compatible_with_to_wide_rows():
    """End-to-end: output feeds directly into to_wide_rows without error."""
    from optionchain_stream.formatters.wide import to_wide_rows
    fetcher = _make_fetcher()
    result = fetcher.fetch_chain("NIFTY", "2026-05-19")
    rows = to_wide_rows(result, underlying="NIFTY", expiry="19MAY26",
                        timestamp=1716000000, lotsize=65)
    assert len(rows) == 2
    assert all(r.lotsize == 65 for r in rows)


# ── Integration test (live Zerodha API) ───────────────────────────────────────

@pytest.mark.integration
def test_integration_fetch_nifty_chain():
    from kiteconnect import KiteConnect
    api_key = os.environ.get("ZERODHA_API_KEY", "qtq5zs1vk4lvfct6")
    access_token = os.environ.get("ZERODHA_ACCESS_TOKEN", "oUVa6cz6S0LrneGxrkpO0xkvfXfT7pJ1")

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    fetcher = ZerodhaChainFetcher(kite_client=kite, instrument_cache_dir="/tmp")
    fetcher.refresh_instrument_master()

    result = fetcher.fetch_chain("NIFTY", "2026-05-19")

    assert result["spot_price"] > 20000, "NIFTY spot should be > 20000"
    assert len(result["strikes"]) > 10, "Should have many strikes"

    strike = result["strikes"][0]
    ce = strike["call_options"]
    pe = strike["put_options"]

    assert ce["ltp"] >= 0
    assert pe["ltp"] >= 0
    assert ce["option_greeks"]["iv"] >= 0
    assert pe["option_greeks"]["iv"] >= 0

    # Must plug into formatter without error
    from optionchain_stream.formatters.wide import to_wide_rows
    rows = to_wide_rows(result, underlying="NIFTY", expiry="19MAY26",
                        timestamp=1716000000, lotsize=65)
    assert len(rows) == len(result["strikes"])
