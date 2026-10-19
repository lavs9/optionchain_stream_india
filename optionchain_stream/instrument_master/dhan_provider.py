"""Dhan instrument master (public scrip-master CSV) -> Instrument objects.

Source: https://images.dhan.co/api-data/api-scrip-master-detailed.csv (public file; not a Data
API call, needs no login). Columns used: EXCH_ID, SEGMENT, SECURITY_ID, INSTRUMENT,
UNDERLYING_SYMBOL, SYMBOL_NAME, DISPLAY_NAME, LOT_SIZE, SM_EXPIRY_DATE, STRIKE_PRICE,
OPTION_TYPE, TICK_SIZE.

Instrument fields as filled here:
  exchange          Dhan segment name: NSE_FNO / BSE_FNO / IDX_I / NSE_EQ / BSE_EQ / MCX_COMM
  token             SECURITY_ID (str)            broker_token  same
  symbol            DISPLAY_NAME (or SYMBOL_NAME)
  name              UNDERLYING_SYMBOL for derivatives, SYMBOL_NAME for indices/equities
  underlying_symbol UNDERLYING_SYMBOL ("" for indices)
  expiry            SM_EXPIRY_DATE as a naive datetime (None if absent)
  strike            STRIKE_PRICE (0.0 for futures/indices)
  lot_size          LOT_SIZE
  instrument_type   "CE" / "PE" for options, "FUT" for futures, "INDEX", "EQ", else INSTRUMENT

No pandas and no Redis: the download is parsed with the csv module and cached in memory
(per provider instance, refreshed when `max_age_s` has passed).
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import logging
import time
from typing import Callable, Dict, Iterable, List, Optional

from optionchain_stream.instrument_master.instrument_provider import InstrumentProvider
from optionchain_stream.models import Instrument

log = logging.getLogger(__name__)

SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

_SEGMENT = {("NSE", "D"): "NSE_FNO", ("BSE", "D"): "BSE_FNO", ("NSE", "E"): "NSE_EQ",
            ("BSE", "E"): "BSE_EQ", ("MCX", "M"): "MCX_COMM"}
OPTION_INSTRUMENTS = {"OPTIDX", "OPTSTK", "OPTFUT", "OPTCUR"}
FUTURE_INSTRUMENTS = {"FUTIDX", "FUTSTK", "FUTCOM", "FUTCUR"}


def _segment(exch: str, seg: str) -> str:
    if seg == "I":
        return "IDX_I"
    return _SEGMENT.get((exch, seg), f"{exch}_{seg}")


def _f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _expiry(v) -> Optional[_dt.datetime]:
    v = (v or "").strip()
    if not v or v.startswith("0001") or v == "-1":
        return None
    try:
        return _dt.datetime.fromisoformat(v[:10])
    except ValueError:
        return None


def parse_scrip_master(text: str, underlyings: Optional[Iterable[str]] = None) -> List[Instrument]:
    """Parse the detailed scrip master. `underlyings` (optional) keeps only those indices and
    their derivatives (matched on UNDERLYING_SYMBOL / SYMBOL_NAME)."""
    keep = set(underlyings) if underlyings is not None else None
    out: List[Instrument] = []
    for row in csv.DictReader(io.StringIO(text)):
        inst_kind = (row.get("INSTRUMENT") or "").strip()
        exch = (row.get("EXCH_ID") or "").strip()
        seg = (row.get("SEGMENT") or "").strip()
        und = (row.get("UNDERLYING_SYMBOL") or "").strip()
        sym_name = (row.get("SYMBOL_NAME") or "").strip()
        sid = (row.get("SECURITY_ID") or "").strip()
        if not sid:
            continue
        if inst_kind in OPTION_INSTRUMENTS:
            opt = (row.get("OPTION_TYPE") or "").strip().upper()
            if opt not in ("CE", "PE"):
                continue
            itype, name = opt, und
        elif inst_kind in FUTURE_INSTRUMENTS:
            itype, name = "FUT", und
        elif inst_kind == "INDEX":
            itype, name, und = "INDEX", sym_name, ""
        elif inst_kind == "EQUITY":
            itype, name = "EQ", sym_name
        else:
            itype, name = inst_kind, und or sym_name
        if keep is not None and name not in keep:
            continue
        out.append(Instrument(
            exchange=_segment(exch, seg),
            token=sid,
            symbol=(row.get("DISPLAY_NAME") or sym_name or sid).strip(),
            name=name,
            expiry=_expiry(row.get("SM_EXPIRY_DATE")),
            strike=_f(row.get("STRIKE_PRICE")) if itype in ("CE", "PE") else 0.0,
            lot_size=int(_f(row.get("LOT_SIZE"), 0)),
            instrument_type=itype,
            broker_token=sid,
            tick_size=_f(row.get("TICK_SIZE")),
            underlying_symbol=und,
            exch_id=exch,
        ))
    return out


def _download(url: str = SCRIP_MASTER_URL, timeout: float = 120.0) -> str:
    import requests
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


class DhanInstrumentProvider(InstrumentProvider):
    def __init__(self, url: str = SCRIP_MASTER_URL, *, underlyings: Optional[Iterable[str]] = None,
                 max_age_s: float = 6 * 3600, fetch_text: Optional[Callable[[], str]] = None,
                 clock: Callable[[], float] = time.time):
        """`fetch_text` overrides the download (tests, or a file the caller already caches)."""
        self.url = url
        self.underlyings = tuple(underlyings) if underlyings is not None else None
        self.max_age_s = max_age_s
        self._fetch_text = fetch_text or (lambda: _download(self.url))
        self._clock = clock
        self._loaded_at: Optional[float] = None
        self._instruments: List[Instrument] = []
        self.instruments_map: Dict[str, Instrument] = {}
        self.symbol_map: Dict[str, Instrument] = {}

    def fetch_instruments(self, exchange: str = "") -> List[Instrument]:
        """All parsed instruments (cached). `exchange` filters on the segment name if given."""
        now = self._clock()
        if self._loaded_at is None or now - self._loaded_at > self.max_age_s:
            insts = parse_scrip_master(self._fetch_text(), self.underlyings)
            self._instruments = insts
            self.instruments_map = {i.token: i for i in insts}
            self.symbol_map = {i.symbol: i for i in insts}
            self._loaded_at = now
            log.info("Dhan scrip master loaded: %d instruments", len(insts))
        if exchange:
            return [i for i in self._instruments if i.exchange == exchange]
        return self._instruments

    def get_instrument_by_token(self, token) -> Optional[Instrument]:
        if not self.instruments_map:
            self.fetch_instruments()
        return self.instruments_map.get(str(token))

    def get_instrument_by_symbol(self, symbol: str) -> Optional[Instrument]:
        if not self.symbol_map:
            self.fetch_instruments()
        return self.symbol_map.get(symbol)

    def nearest_expiries(self, underlying: str, n: int,
                         today: Optional[_dt.date] = None) -> List[_dt.date]:
        return nearest_expiries(self.fetch_instruments(), underlying, n, today)


def nearest_expiries(instruments: Iterable[Instrument], underlying: str, n: int,
                     today: Optional[_dt.date] = None) -> List[_dt.date]:
    """The `n` nearest option expiries (>= today) of `underlying`, ascending."""
    today = today or _dt.date.today()
    exps = sorted({i.expiry.date() for i in instruments
                   if i.name == underlying and i.instrument_type in ("CE", "PE")
                   and i.expiry is not None and i.expiry.date() >= today})
    return exps[:max(0, n)]
