from abc import ABC, abstractmethod
from datetime import date
from typing import List, Dict
from optionchain_stream.models import Instrument


class InstrumentProvider(ABC):
    @abstractmethod
    def fetch_instruments(self, exchange: str = 'NFO') -> List[Instrument]:
        """Fetch and parse instruments from the broker's master source."""
        pass

    @abstractmethod
    def get_instrument_by_token(self, token: int) -> Instrument:
        pass

    @abstractmethod
    def get_instrument_by_symbol(self, symbol: str) -> Instrument:
        pass

    def _matches_underlying(self, inst, underlying: str) -> bool:
        """True if ``inst`` belongs to the given F&O underlying.

        Matches by ``underlying_symbol`` (the listed trading symbol most callers
        pass, e.g. "RELIANCE") and falls back to ``name`` for brokers/providers
        that pre-normalise ``name`` to the underlying (index options such as
        "NIFTY").  Stock option rows from Upstox carry the company's full name
        in ``name`` ("RELIANCE INDUSTRIES LTD") so the underlying_symbol match
        is what makes stock F&O work.
        """
        return inst.underlying_symbol == underlying or (
            not inst.underlying_symbol and inst.name == underlying
        )

    def get_active_expiries(self, underlying: str) -> list[str]:
        """
        Return sorted ISO-date strings of future expiries for the given underlying.
        Derived from fetch_instruments(); providers cache the download so repeat
        calls are cheap.  Returns YYYY-MM-DD strings compatible with all broker APIs.
        """
        instruments = self.fetch_instruments()
        today = date.today()
        seen: set[str] = set()
        for inst in instruments:
            if (
                self._matches_underlying(inst, underlying)
                and inst.instrument_type in ('CE', 'PE')
                and inst.expiry is not None
                and inst.expiry.date() >= today
            ):
                seen.add(inst.expiry.strftime('%Y-%m-%d'))
        return sorted(seen)

    def get_lotsize(self, underlying: str) -> int:
        """
        Return lot size for the underlying (first CE/PE match).
        Derived from fetch_instruments().  Returns 0 if not found.
        """
        instruments = self.fetch_instruments()
        for inst in instruments:
            if self._matches_underlying(inst, underlying) and inst.instrument_type in ('CE', 'PE'):
                return inst.lot_size
        return 0
