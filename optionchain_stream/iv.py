"""Implied volatility (IV only; greeks are out of scope) for European index options.

Model: Black-76 on the FORWARD of the expiry, never on spot.
  * Forward: the caller's future price for that expiry if given (> 0), else a put-call-parity
    forward F = K + e^{rT} (C - P), median over the `parity_strikes` strikes nearest the spot
    that have a usable price on both legs.
  * Rate: passed in by the caller (continuously compounded, e.g. 0.055). No default.
  * Dividends: none (the forward already carries them).
  * Time: calendar minutes from `now` to the expiry's 15:30 IST close, / 525,600 (365-day year).
    Under one minute (but not past the close) counts as one minute; at or after the close the
    expiry is "expired".
  * Side: per strike, only the OTM leg is solved (call if K >= F, put if K < F).
  * Price per leg (`leg_price`): mid of level-1 bid/ask when both are > 0 and the spread is
    <= `max_spread_frac` of the mid; else the LTP if > 0; else no price.
  * Solver: Brent's method on sigma in [1e-4, 5.0].
  * Failure: iv = None plus a reason, never 0.0. Reasons: no_price, no_forward, expired,
    below_intrinsic, above_max_price, out_of_range, not_converged, bad_input.

This module never writes vendor fields; its results are a separate, derived output.
"""
from __future__ import annotations

import datetime as _dt
import math
import statistics
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
EXPIRY_CLOSE_IST = _dt.time(15, 30)
MINUTES_PER_YEAR = 365 * 24 * 60   # 525,600
SIGMA_LO, SIGMA_HI = 1e-4, 5.0

NO_PRICE = "no_price"
NO_FORWARD = "no_forward"
EXPIRED = "expired"
BELOW_INTRINSIC = "below_intrinsic"
ABOVE_MAX_PRICE = "above_max_price"
OUT_OF_RANGE = "out_of_range"
NOT_CONVERGED = "not_converged"
BAD_INPUT = "bad_input"


@dataclass(frozen=True)
class IVResult:
    iv: Optional[float]
    reason: Optional[str] = None      # None when iv is set

    @property
    def ok(self) -> bool:
        return self.iv is not None


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def year_fraction(now: _dt.datetime, expiry: _dt.date,
                  close: _dt.time = EXPIRY_CLOSE_IST) -> float:
    """Calendar minutes from `now` (aware) to `expiry` at `close` IST, / 525,600. 0.0 if the
    expiry has closed; at least one minute otherwise."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    end = _dt.datetime.combine(expiry, close, IST)
    minutes = (end - now).total_seconds() / 60.0
    if minutes <= 0:
        return 0.0
    return max(minutes, 1.0) / MINUTES_PER_YEAR


def black76_price(F: float, K: float, T: float, r: float, sigma: float, is_call: bool) -> float:
    df = math.exp(-r * T)
    if sigma <= 0 or T <= 0:
        return df * max(F - K, 0.0) if is_call else df * max(K - F, 0.0)
    sd = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sd * sd) / sd
    d2 = d1 - sd
    if is_call:
        return df * (F * _ncdf(d1) - K * _ncdf(d2))
    return df * (K * _ncdf(-d2) - F * _ncdf(-d1))


def _brent(f, a: float, b: float, tol: float, max_iter: int) -> Optional[float]:
    fa, fb = f(a), f(b)
    if fa * fb > 0:
        return None
    if abs(fa) < abs(fb):
        a, b, fa, fb = b, a, fb, fa
    c, fc, mflag, d = a, fa, True, 0.0
    for _ in range(max_iter):
        if fb == 0 or abs(b - a) < tol:
            return b
        if fa != fc and fb != fc:
            s = (a * fb * fc / ((fa - fb) * (fa - fc)) + b * fa * fc / ((fb - fa) * (fb - fc))
                 + c * fa * fb / ((fc - fa) * (fc - fb)))
        else:
            s = b - fb * (b - a) / (fb - fa)
        cond = (not ((3 * a + b) / 4 < s < b or b < s < (3 * a + b) / 4)
                or (mflag and abs(s - b) >= abs(b - c) / 2)
                or (not mflag and abs(s - b) >= abs(c - d) / 2)
                or (mflag and abs(b - c) < tol) or (not mflag and abs(c - d) < tol))
        if cond:
            s, mflag = (a + b) / 2, True
        else:
            mflag = False
        fs = f(s)
        d, c, fc = c, b, fb
        if fa * fs < 0:
            b, fb = s, fs
        else:
            a, fa = s, fs
        if abs(fa) < abs(fb):
            a, b, fa, fb = b, a, fb, fa
    return None


def implied_vol(price: Optional[float], F: Optional[float], K: float, T: float, r: float,
                is_call: bool, *, tol: float = 1e-10, max_iter: int = 200) -> IVResult:
    """Black-76 IV of one option. Never returns 0.0: failures give iv=None and a reason."""
    if price is None or not price > 0 or math.isnan(price):
        return IVResult(None, NO_PRICE)
    if F is None or not F > 0:
        return IVResult(None, NO_FORWARD)
    if not K > 0 or any(map(math.isnan, (F, K, T, r))):
        return IVResult(None, BAD_INPUT)
    if T <= 0:
        return IVResult(None, EXPIRED)
    df = math.exp(-r * T)
    intrinsic = df * (max(F - K, 0.0) if is_call else max(K - F, 0.0))
    upper = df * (F if is_call else K)
    if price < intrinsic - 1e-12:
        return IVResult(None, BELOW_INTRINSIC)
    if price >= upper:
        return IVResult(None, ABOVE_MAX_PRICE)

    def f(s):
        return black76_price(F, K, T, r, s, is_call) - price

    if f(SIGMA_LO) > 0 or f(SIGMA_HI) < 0:
        return IVResult(None, OUT_OF_RANGE)
    s = _brent(f, SIGMA_LO, SIGMA_HI, tol, max_iter)
    if s is None:
        return IVResult(None, NOT_CONVERGED)
    return IVResult(s)


def leg_price(leg, max_spread_frac: float = 0.10) -> tuple[Optional[float], Optional[str]]:
    """(price, kind) for a leg-like object with bid/ask/ltp attributes; kind 'mid' | 'ltp'."""
    if leg is None:
        return None, None
    bid, ask, ltp = getattr(leg, "bid", None), getattr(leg, "ask", None), getattr(leg, "ltp", None)
    if bid and ask and bid > 0 and ask >= bid:
        mid = (bid + ask) / 2.0
        if (ask - bid) <= max_spread_frac * mid:
            return mid, "mid"
    if ltp and ltp > 0:
        return float(ltp), "ltp"
    return None, None


def parity_forward(pairs: Iterable[tuple[float, Optional[float], Optional[float]]],
                   T: float, r: float, spot_hint: Optional[float] = None,
                   n: int = 3) -> Optional[float]:
    """Median over the `n` strikes nearest `spot_hint` (or the middle strike) of
    K + e^{rT} (C - P), using only strikes where both prices are > 0."""
    usable = [(k, c, p) for k, c, p in pairs if c and p and c > 0 and p > 0]
    if not usable:
        return None
    if spot_hint is None or not spot_hint > 0:
        ks = sorted(k for k, _, _ in usable)
        spot_hint = ks[len(ks) // 2]
    usable.sort(key=lambda t: abs(t[0] - spot_hint))
    growth = math.exp(r * T)
    vals = [k + growth * (c - p) for k, c, p in usable[:max(1, n)]]
    fwd = statistics.median(vals)
    return fwd if fwd > 0 else None


@dataclass(frozen=True)
class StrikeIV:
    strike: float
    side: Optional[str]          # "CE" | "PE" (the OTM leg solved), None without a forward
    price: Optional[float]
    price_kind: Optional[str]    # "mid" | "ltp"
    iv: Optional[float]
    reason: Optional[str]


@dataclass(frozen=True)
class ExpiryIV:
    underlying: str
    expiry: _dt.date
    forward: Optional[float]
    forward_kind: Optional[str]  # "future" | "parity"
    t_years: float
    rate: float
    strikes: tuple               # StrikeIV, ascending strike


def chain_iv(expiry_snapshot, *, now: _dt.datetime, rate: float,
             future_price: Optional[float] = None, parity_strikes: int = 3,
             max_spread_frac: float = 0.10) -> ExpiryIV:
    """IV for every strike of one chain_state.ExpirySnapshot (or any object with underlying,
    expiry, spot, future, strikes[.strike/.ce/.pe]). `future_price` overrides the snapshot's
    future; pass None to use the snapshot's future LTP if it has one, else parity."""
    es = expiry_snapshot
    T = year_fraction(now, es.expiry)
    rows = []
    for s in es.strikes:
        c, _ = leg_price(s.ce, max_spread_frac)
        p, _ = leg_price(s.pe, max_spread_frac)
        rows.append((s.strike, c, p))
    fwd, kind = None, None
    fut = future_price
    if fut is None and getattr(es, "future", None) is not None:
        fut = getattr(es.future, "ltp", None)
    if fut is not None and fut > 0:
        fwd, kind = float(fut), "future"
    elif T > 0:
        fwd = parity_forward(rows, T, rate, getattr(es, "spot", None), parity_strikes)
        kind = "parity" if fwd is not None else None
    out = []
    for s in es.strikes:
        if T <= 0:
            out.append(StrikeIV(s.strike, None, None, None, None, EXPIRED))
            continue
        if fwd is None:
            out.append(StrikeIV(s.strike, None, None, None, None, NO_FORWARD))
            continue
        is_call = s.strike >= fwd
        leg = s.ce if is_call else s.pe
        price, pkind = leg_price(leg, max_spread_frac)
        res = implied_vol(price, fwd, s.strike, T, rate, is_call)
        out.append(StrikeIV(s.strike, "CE" if is_call else "PE", price, pkind, res.iv, res.reason))
    return ExpiryIV(es.underlying, es.expiry, fwd, kind, T, rate, tuple(out))
