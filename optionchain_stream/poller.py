from __future__ import annotations

import logging
import time

from optionchain_stream.formatters.wide import to_wide_rows
from optionchain_stream.models import CycleHealth, OptionChainRow

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
        Formats to WIDE rows. Applies quality_flag.
        Returns (rows, health). Does NOT write anywhere.
        """
        start_ms = int(time.monotonic() * 1000)
        timestamp = int(time.time())

        all_rows: list[OptionChainRow] = []
        symbols_received = 0
        gaps = 0
        stale_warnings = 0
        first_error: str | None = None

        for underlying in self._symbols:
            expiries = self.active_expiries(underlying)
            if not expiries:
                expiries = [""]  # fallback — let the broker decide

            success = False
            for expiry in expiries:
                try:
                    chain = self._coordinator.fetch_chain(underlying, expiry)
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
        )
        return all_rows, health

    def _get_lotsize(self, underlying: str) -> int:
        try:
            provider = self._coordinator.get_instrument_provider()
            return provider.get_lotsize(underlying)
        except Exception:
            return 0
