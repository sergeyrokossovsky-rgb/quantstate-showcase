"""qs_feedlag — where does a market-data delay come from? (portfolio sample)

Input: per-instrument CSV rows written every 10 s by ``ninjascript/FeedLagMonitor.cs`` (utc, symbol, lag_max_s, …).
Output: lag episodes per instrument, each classified by what the OTHER instruments did at the same moment:

* ``shared``  — at least one other instrument fell behind too → upstream: network, data feed or the whole PC;
* ``local``   — the others stayed current → this instrument's processing inside the platform;
* ``mixed`` / ``unknown`` — partial overlap, or no other instrument recorded.

A growth rate (s of lag per minute) separates a building queue (backlog, rate ≈ tens of s/min) from a constant offset.

Author: Sergei Rokossovskii (QuantState LLC). No proprietary trading logic or data.
"""
from .episodes import Episode, classify, find_episodes, load_csv, summary

__all__ = ["Episode", "classify", "find_episodes", "load_csv", "summary"]
