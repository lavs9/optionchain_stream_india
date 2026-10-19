"""Pick what to stream: every strike (CE+PE) of the N nearest expiries per underlying, plus
the index and (optionally) the futures, as FeedInstrument (for DhanMarketFeed) and
ContractMeta (for ChainAssembler) lists."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from optionchain_stream.chain_state import ContractMeta
from optionchain_stream.dhan import packets as P
from optionchain_stream.dhan.feed import FeedInstrument
from optionchain_stream.instrument_master.dhan_provider import nearest_expiries
from optionchain_stream.models import Instrument

# derivative exchange of each index (SENSEX derivatives are on BSE)
DEFAULT_DERIVATIVE_SEGMENT = {"NIFTY": "NSE_FNO", "BANKNIFTY": "NSE_FNO", "FINNIFTY": "NSE_FNO",
                              "MIDCPNIFTY": "NSE_FNO", "SENSEX": "BSE_FNO", "BANKEX": "BSE_FNO"}
# exchange whose index row is the underlying (Dhan lists some indices on both)
_INDEX_EXCHANGE = {"NSE_FNO": "NSE", "BSE_FNO": "BSE"}


@dataclass(frozen=True)
class Universe:
    feed: tuple            # FeedInstrument
    contracts: tuple       # ContractMeta (same instruments)
    expiries: dict         # underlying -> [date, ...] chosen

    @property
    def option_count(self) -> int:
        return sum(1 for c in self.contracts if c.option_type in ("CE", "PE"))


def _seg_code(name: str) -> int:
    return P.SEGMENT_CODES[name]


def near_expiry_universe(instruments: Sequence[Instrument], underlyings: Iterable[str], n: int, *,
                         today: Optional[_dt.date] = None, include_index: bool = True,
                         include_futures: str = "nearest",
                         derivative_segment: Optional[dict] = None,
                         index_rows: Optional[dict] = None) -> Universe:
    """All CE+PE contracts of the `n` nearest live expiries of each underlying.

    include_futures: "none" | "nearest" (the nearest live future) | "matching" (futures whose
    expiry is one of the chosen option expiries). `index_rows` optionally maps underlying ->
    Instrument of its index when the master has several candidates."""
    today = today or _dt.date.today()
    segs = {**DEFAULT_DERIVATIVE_SEGMENT, **(derivative_segment or {})}
    feed: list[FeedInstrument] = []
    contracts: list[ContractMeta] = []
    chosen: dict[str, list[_dt.date]] = {}
    for und in underlyings:
        seg_name = segs.get(und, "NSE_FNO")
        derivs = [i for i in instruments if i.name == und and i.exchange == seg_name]
        exps = nearest_expiries(derivs, und, n, today)
        chosen[und] = exps
        wanted = set(exps)
        for i in sorted((i for i in derivs if i.instrument_type in ("CE", "PE")
                         and i.expiry is not None and i.expiry.date() in wanted),
                        key=lambda i: (i.expiry, i.strike, i.instrument_type)):
            exp = i.expiry.date()
            meta = ContractMeta(_seg_code(i.exchange), int(i.token), und, i.instrument_type,
                                exp, i.strike, i.symbol, i.lot_size)
            contracts.append(meta)
            feed.append(FeedInstrument(meta.segment, meta.security_id, group=f"{und}|{exp}"))
        if include_futures != "none":
            futs = sorted((i for i in derivs if i.instrument_type == "FUT"
                           and i.expiry is not None and i.expiry.date() >= today),
                          key=lambda i: i.expiry)
            if include_futures == "nearest":
                futs = futs[:1]
            else:
                futs = [f for f in futs if f.expiry.date() in wanted]
            for f in futs:
                meta = ContractMeta(_seg_code(f.exchange), int(f.token), und, "FUT",
                                    f.expiry.date(), 0.0, f.symbol, f.lot_size)
                contracts.append(meta)
                feed.append(FeedInstrument(meta.segment, meta.security_id, group=f"{und}|index"))
        if include_index:
            idx = (index_rows or {}).get(und)
            if idx is None:
                exch = _INDEX_EXCHANGE.get(seg_name, "NSE")
                cands = [i for i in instruments if i.instrument_type == "INDEX" and i.name == und]
                idx = next((i for i in cands if i.exch_id == exch), None) or (
                    cands[0] if cands else None)
            if idx is not None:
                meta = ContractMeta(P.IDX_I, int(idx.token), und, "INDEX", None, 0.0,
                                    idx.symbol, 0)
                contracts.append(meta)
                feed.append(FeedInstrument(P.IDX_I, meta.security_id, group=f"{und}|index"))
    return Universe(tuple(feed), tuple(contracts), chosen)
