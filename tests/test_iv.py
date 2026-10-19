"""Black-76 IV: textbook reference values, failure reasons (never 0.0), time convention,
parity forward and the OTM-side rule."""
import datetime as dt
import math
from types import SimpleNamespace as NS

import pytest

from optionchain_stream import iv as IV

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def test_reference_bs_equivalent():
    # Black-Scholes S=100,K=100,T=1,r=5%,sigma=20% call = 10.450583572 (Hull); Black-76 with
    # F = S e^{rT} must give the same price and invert to 0.20.
    F = 100 * math.exp(0.05)
    assert IV.black76_price(F, 100, 1.0, 0.05, 0.20, True) == pytest.approx(10.450583572, abs=1e-8)
    res = IV.implied_vol(10.450583572, F, 100, 1.0, 0.05, True)
    assert res.ok and res.reason is None and res.iv == pytest.approx(0.20, abs=1e-8)


def test_reference_hull_futures_put():
    # Hull, futures option example: F=K=20, r=9%, T=4 months, sigma=25% -> put 1.1166
    p = IV.black76_price(20, 20, 4 / 12, 0.09, 0.25, False)
    assert p == pytest.approx(1.11664, abs=5e-5)
    assert IV.implied_vol(p, 20, 20, 4 / 12, 0.09, False).iv == pytest.approx(0.25, abs=1e-8)


@pytest.mark.parametrize("sigma", [0.05, 0.12, 0.5, 1.5, 3.0])
@pytest.mark.parametrize("is_call,K", [(True, 26000.0), (False, 24000.0), (True, 25000.0)])
def test_roundtrip(sigma, is_call, K):
    F, T, r = 25000.0, 7 / 365, 0.055
    price = IV.black76_price(F, K, T, r, sigma, is_call)
    res = IV.implied_vol(price, F, K, T, r, is_call)
    if res.ok:
        assert res.iv == pytest.approx(sigma, rel=1e-6)
    else:  # deep OTM low-vol prices underflow; must still never be 0.0
        assert res.iv is None and res.reason


@pytest.mark.parametrize("args,reason", [
    ((None, 100, 100, 0.1, 0.05, True), IV.NO_PRICE),
    ((0.0, 100, 100, 0.1, 0.05, True), IV.NO_PRICE),
    ((float("nan"), 100, 100, 0.1, 0.05, True), IV.NO_PRICE),
    ((5.0, None, 100, 0.1, 0.05, True), IV.NO_FORWARD),
    ((5.0, 0.0, 100, 0.1, 0.05, True), IV.NO_FORWARD),
    ((5.0, 100, 0.0, 0.1, 0.05, True), IV.BAD_INPUT),
    ((5.0, 100, 100, 0.0, 0.05, True), IV.EXPIRED),
    ((1.0, 120, 100, 0.1, 0.05, True), IV.BELOW_INTRINSIC),
    ((101.0, 100, 100, 0.1, 0.05, True), IV.ABOVE_MAX_PRICE),
    ((99.0, 100, 100, 0.1, 0.0, True), IV.OUT_OF_RANGE),       # needs sigma > 5
])
def test_failure_reasons_never_zero(args, reason):
    res = IV.implied_vol(*args)
    assert res.iv is None and res.reason == reason and not res.ok


def test_year_fraction_calendar_minutes_to_1530_ist():
    exp = dt.date(2026, 10, 20)
    now = dt.datetime(2026, 10, 19, 15, 30, tzinfo=IST)
    assert IV.year_fraction(now, exp) == pytest.approx(1440 / 525600)
    assert IV.year_fraction(dt.datetime(2026, 10, 20, 15, 29, 50, tzinfo=IST), exp) == \
        pytest.approx(1 / 525600)                                     # 1-minute floor
    assert IV.year_fraction(dt.datetime(2026, 10, 20, 15, 30, tzinfo=IST), exp) == 0.0
    # aware UTC input is the same instant
    assert IV.year_fraction(now.astimezone(dt.timezone.utc), exp) == pytest.approx(1440 / 525600)
    with pytest.raises(ValueError):
        IV.year_fraction(dt.datetime(2026, 10, 19, 15, 30), exp)


def test_leg_price_mid_or_ltp():
    assert IV.leg_price(NS(bid=99.0, ask=101.0, ltp=50.0)) == (100.0, "mid")
    assert IV.leg_price(NS(bid=80.0, ask=120.0, ltp=95.0)) == (95.0, "ltp")   # spread 40%
    assert IV.leg_price(NS(bid=None, ask=None, ltp=None)) == (None, None)
    assert IV.leg_price(None) == (None, None)


def test_parity_forward_median_near_spot():
    F, T, r = 25100.0, 0.02, 0.055
    df = math.exp(-r * T)
    pairs = [(k, df * max(F - k, 0) + 50, df * max(k - F, 0) + 50) for k in
             (24800.0, 24900.0, 25000.0, 25100.0, 25200.0)]
    pairs.append((26000.0, None, 10.0))
    assert IV.parity_forward(pairs, T, r, spot_hint=25050.0) == pytest.approx(F)
    assert IV.parity_forward([(25000.0, None, 5.0)], T, r) is None


def _leg(price):
    return NS(bid=None, ask=None, ltp=price)


def _chain(F, T, r, sigma, strikes, future=None, spot=None):
    exp = dt.date(2026, 10, 27)
    rows = [NS(strike=k, ce=_leg(IV.black76_price(F, k, T, r, sigma, True)),
               pe=_leg(IV.black76_price(F, k, T, r, sigma, False))) for k in strikes]
    return NS(underlying="NIFTY", expiry=exp, spot=spot, future=future, strikes=rows)


def test_chain_iv_parity_forward_and_otm_side():
    exp_close = dt.datetime(2026, 10, 27, 15, 30, tzinfo=IST)
    now = exp_close - dt.timedelta(days=8)
    T = IV.year_fraction(now, dt.date(2026, 10, 27))
    F, r, sig = 25120.0, 0.055, 0.14
    es = _chain(F, T, r, sig, [24800.0, 25000.0, 25100.0, 25200.0, 25400.0], spot=25080.0)
    out = IV.chain_iv(es, now=now, rate=r)
    assert out.forward_kind == "parity" and out.forward == pytest.approx(F, abs=1e-6)
    assert [s.side for s in out.strikes] == ["PE", "PE", "PE", "CE", "CE"]
    for s in out.strikes:
        assert s.iv == pytest.approx(sig, rel=1e-6) and s.reason is None and s.price_kind == "ltp"


def test_chain_iv_uses_future_and_reports_missing_prices():
    now = dt.datetime(2026, 10, 19, 12, 0, tzinfo=IST)
    es = _chain(25000.0, 0.02, 0.055, 0.15, [25000.0, 25200.0], future=NS(ltp=25010.0))
    es.strikes[1].ce = _leg(None)
    out = IV.chain_iv(es, now=now, rate=0.055)
    assert out.forward_kind == "future" and out.forward == 25010.0
    assert out.strikes[1].iv is None and out.strikes[1].reason == IV.NO_PRICE
    assert out.strikes[0].iv is not None and out.strikes[0].iv > 0


def test_chain_iv_without_forward_or_after_expiry():
    es = _chain(25000.0, 0.02, 0.055, 0.15, [25000.0])
    es.strikes[0].ce = _leg(None)
    out = IV.chain_iv(es, now=dt.datetime(2026, 10, 19, 12, 0, tzinfo=IST), rate=0.055)
    assert out.forward is None and out.strikes[0].reason == IV.NO_FORWARD
    late = IV.chain_iv(es, now=dt.datetime(2026, 10, 28, 9, 0, tzinfo=IST), rate=0.055)
    assert late.t_years == 0.0 and late.strikes[0].reason == IV.EXPIRED and late.strikes[0].iv is None
