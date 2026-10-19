"""Stream the N nearest expiries of NIFTY / BANKNIFTY / SENSEX from the Dhan v2 feed and print a
1-minute chain snapshot with Black-76 IV. Never logs in: DHAN_ACCESS_TOKEN must already exist.

    pip install -e ".[dhan]"
    DHAN_CLIENT_ID=... DHAN_ACCESS_TOKEN=... python examples/dhan_chain_stream.py
"""
import asyncio
import datetime as dt
import os

from optionchain_stream.chain_state import ChainAssembler, MinuteSnapshotter
from optionchain_stream.dhan import DhanMarketFeed, near_expiry_universe
from optionchain_stream.instrument_master.dhan_provider import DhanInstrumentProvider
from optionchain_stream.iv import chain_iv

RATE = 0.055   # caller-supplied, continuously compounded


async def main():
    insts = DhanInstrumentProvider(underlyings=["NIFTY", "BANKNIFTY", "SENSEX"]).fetch_instruments()
    uni = near_expiry_universe(insts, ["NIFTY", "BANKNIFTY", "SENSEX"], 5)
    print("instruments:", len(uni.feed), "options:", uni.option_count, uni.expiries)

    assembler = ChainAssembler(uni.contracts)
    feed = DhanMarketFeed(os.environ["DHAN_CLIENT_ID"], lambda: os.environ["DHAN_ACCESS_TOKEN"],
                          uni.feed, on_packet=assembler.on_packet, on_event=print)

    def on_snapshot(snap):
        for es in snap.expiries:
            ivs = chain_iv(es, now=snap.at, rate=RATE)
            ok = sum(s.iv is not None for s in ivs.strikes)
            print(snap.at, es.underlying, es.expiry, "spot", es.spot, "fwd", ivs.forward,
                  ivs.forward_kind, f"iv {ok}/{len(ivs.strikes)}")

    snapper = MinuteSnapshotter(assembler, on_snapshot)
    await asyncio.gather(feed.run(), snapper.run())


if __name__ == "__main__":
    asyncio.run(main())
