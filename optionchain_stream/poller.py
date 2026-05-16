from __future__ import annotations

import logging
import time

from optionchain_stream.formatters.wide import to_wide_rows
from optionchain_stream.models import CycleHealth, OptionChainRow
from optionchain_stream.analytics.straddle import compute_atm_straddle, compute_synthetic_futures_spread
from optionchain_stream.analytics.gex import compute_gex_flip
from optionchain_stream.analytics.pcr import compute_oi_zones
from optionchain_stream.analytics.max_pain import compute_max_pain

log = logging.getLogger(__name__)


class OptionChainPoller:
    """
    Wraps BrokerCoordinator + WIDE formatter.
    poll_once() is a blocking synchronous call — no internal loop, no writes.
    Pipeline daemon calls this from a thread-pool executor every interval_sec.
    """

    def __init__(
        self,
        broker_coordinator,
        symbols: list[str],
        market_calendar,
        interval_sec: int = 300,
        jitter_sec: int = 10,
    ):
        self._coordinator = broker_coordinator
        self._symbols = symbols
        self._calendar = market_calendar
        self.interval_sec = interval_sec
        self.jitter_sec = jitter_sec
        self._prev_snapshots: dict[tuple[str, str], dict[float, OptionChainRow]] = {}

    def is_market_open(self) -> bool:
        return self._calendar.is_market_open()

    def active_expiries(self, underlying: str) -> list[str]:
        try:
            provider = self._coordinator.get_instrument_provider()
            return provider.get_active_expiries(underlying)
        except Exception:
            log.warning("Could not get active expiries for %s", underlying)
            return []

    def poll_once(self) -> tuple[list[OptionChainRow], CycleHealth]:
        """
        Fetch all underlyings for all active expiries.
        Formats to WIDE rows. Applies quality_flag and analytics.
        Returns (rows, health). Does NOT write anywhere.
        """
        start_ms = int(time.monotonic() * 1000)
        timestamp = int(time.time())

        all_rows: list[OptionChainRow] = []
        symbols_received = 0
        gaps = 0
        stale_warnings = 0
        first_error: str | None = None

        # aggregated analytics — last (underlying, expiry) slice wins;
        # callers needing per-expiry values should group rows themselves
        atm_straddle_premium: float | None = None
        synthetic_futures_spread_val: float | None = None
        gex_flip_strike: float | None = None
        oi_zones: dict | None = None
        max_pain_strike: float | None = None

        for underlying in self._symbols:
            expiries = self.active_expiries(underlying)
            if not expiries:
                expiries = [""]  # fallback — let the broker decide

            success = False
            for expiry in expiries:
                try:
                    chain = self._coordinator.fetch_chain(underlying, expiry)
                    spot = float(chain.get("spot_price") or 0.0)
                    key = (underlying, expiry)
                    prev = self._prev_snapshots.get(key)

                    rows = to_wide_rows(
                        chain,
                        underlying=underlying,
                        expiry=expiry,
                        timestamp=timestamp,
                        lotsize=self._get_lotsize(underlying),
                        prev_snapshot=prev,
                    )

                    stale_warnings += sum(1 for r in rows if r.quality_flag == 4)
                    self._prev_snapshots[key] = {r.strike: r for r in rows}
                    all_rows.extend(rows)
                    success = True

                    straddle = compute_atm_straddle(rows, spot)
                    if straddle:
                        atm_straddle_premium = straddle["straddle_premium"]
                        synthetic_futures_spread_val = compute_synthetic_futures_spread(rows, spot)

                    gex_flip_strike = compute_gex_flip(rows, spot)
                    oi_zones = compute_oi_zones(rows)
                    max_pain_strike = compute_max_pain(rows)

                except Exception as exc:
                    msg = f"{underlying}/{expiry}: {exc}"
                    log.exception("poll_once error — %s", msg)
                    if first_error is None:
                        first_error = str(exc)
                    gaps += 1

            if success:
                symbols_received += 1

        duration_ms = int(time.monotonic() * 1000) - start_ms

        health = CycleHealth(
            ts=timestamp,
            cycle_type="option_live",
            symbols_expected=len(self._symbols),
            symbols_received=symbols_received,
            gaps=gaps,
            stale_warnings=stale_warnings,
            duration_ms=duration_ms,
            error=first_error,
            atm_straddle_premium=atm_straddle_premium,
            synthetic_futures_spread=synthetic_futures_spread_val,
            gex_flip_strike=gex_flip_strike,
            oi_zones=oi_zones,
            max_pain_strike=max_pain_strike,
        )
        return all_rows, health

    def _get_lotsize(self, underlying: str) -> int:
        try:
            provider = self._coordinator.get_instrument_provider()
            return provider.get_lotsize(underlying)
        except Exception:
            return 0
