"""Dhan Live Market Feed v2 -> option chain, as a library.

Public API:
    packets      decode_packet, iter_packets, ltt_to_utc, subscribe_messages, segment/request
                 constants, packet dataclasses (Ticker/Quote/OI/PrevClose/Full/Disconnect)
    feed         FeedInstrument, default_mode, plan_connections, shard_messages,
                 DhanMarketFeed, FeedEvent, CapacityError
    universe     near_expiry_universe -> Universe(feed, contracts, expiries)
and, broker-agnostic:
    optionchain_stream.chain_state   ContractMeta, ChainAssembler, MinuteSnapshotter,
                                     ChainSnapshot / ExpirySnapshot / StrikeSnapshot / LegSnapshot
    optionchain_stream.iv            year_fraction, black76_price, implied_vol, parity_forward,
                                     leg_price, chain_iv -> ExpiryIV / StrikeIV / IVResult
"""
import importlib

_EXPORTS = {
    "CapacityError": "feed", "DhanMarketFeed": "feed", "FeedEvent": "feed",
    "FeedInstrument": "feed", "default_mode": "feed", "plan_connections": "feed",
    "shard_messages": "feed", "Universe": "universe", "near_expiry_universe": "universe",
}
__all__ = sorted(_EXPORTS)


def __getattr__(name):  # lazy, so chain_state <-> dhan.packets imports never cycle
    mod = _EXPORTS.get(name)
    if mod is None:
        raise AttributeError(name)
    return getattr(importlib.import_module(f"optionchain_stream.dhan.{mod}"), name)
