"""Threshold-triggered permission window + session-aware time deadline.

A slow "state" score (any 0..100 indicator evaluated once per closed bar) does not choose a trade; it only *opens a window*
in which a faster trigger may act. This module is the bookkeeping for that pattern, written so it can run identically in a
back-test and on a live feed:

* the window opens when the score reaches the threshold while the machine is **armed**;
* inside the window at most ``max_uses`` actions are counted (a use is booked when an action is *filled*, not when it is
  attempted, so a cancelled order does not burn the allowance);
* the machine re-arms only after the score stayed **below** the threshold for ``rearm_bars`` consecutive bars, which stops one
  long excursion from opening a new window every bar;
* the decision for bar *t+1* uses only the state after bar *t* closed (no look-ahead).

``next_deadline`` stamps a wall-clock exit (e.g. 15:00 exchange time) on a position at entry. Stamping at entry matters when
configuration profiles switch during the life of the position: the deadline belongs to the trade, not to the active profile.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo


@dataclass
class WindowState:
    armed: bool = True
    below: int = 0
    window_id: int = 0
    window_end: Optional[datetime] = None
    uses: int = 0


class PermissionWindow:
    def __init__(self, threshold: float, window: timedelta, max_uses: int = 2, rearm_bars: int = 30):
        if not 0 <= threshold <= 100:
            raise ValueError("threshold is on a 0..100 scale")
        self.threshold = threshold
        self.window = window
        self.max_uses = max_uses
        self.rearm_bars = rearm_bars
        self.s = WindowState()

    def on_bar_close(self, score: Optional[float], bar_close: datetime) -> bool:
        """Feed the score of a CLOSED bar. Returns True when a new window opened on this bar. None = score unavailable."""
        s = self.s
        if score is not None and score >= self.threshold:
            s.below = 0
            if s.armed:
                s.armed = False
                s.window_id += 1
                s.window_end = bar_close + self.window
                s.uses = 0
                return True
            return False
        s.below += 1
        if not s.armed and s.below >= self.rearm_bars:
            s.armed = True
        return False

    def allows(self, now: datetime) -> Tuple[bool, str]:
        """May an action be taken now? Returns (allowed, reason)."""
        s = self.s
        if s.window_id == 0 or s.window_end is None or now > s.window_end:
            return False, "wait"
        if self.max_uses > 0 and s.uses >= self.max_uses:
            return False, "max_uses"
        return True, ""

    def book_fill(self, window_id: int) -> None:
        """Count a filled action against the window it was allowed in (stale ids are ignored)."""
        if window_id == self.s.window_id and window_id > 0:
            self.s.uses += 1


def next_deadline(now_utc: datetime, hhmm: int, tz: str = "America/Chicago", quiet_minutes: int = 60) -> Tuple[Optional[datetime], bool]:
    """Next occurrence of HH:MM in exchange time, as UTC. Returns (deadline, inside_quiet_period).

    inside_quiet_period is True during the ``quiet_minutes`` right after the exit time — a caller would refuse new entries then,
    otherwise a trade opened at 15:05 would inherit tomorrow's 15:00 deadline. hhmm <= 0 means "no deadline". DST-safe: the
    arithmetic is done in the exchange time zone, not with a fixed UTC offset.
    """
    if hhmm <= 0:
        return None, False
    hh, mm = divmod(hhmm, 100)
    if not (0 <= hh < 24 and 0 <= mm < 60):
        raise ValueError("hhmm must be HHMM")
    z = ZoneInfo(tz)
    local = now_utc.astimezone(z)
    exit_local = datetime.combine(local.date(), time(hh, mm), tzinfo=z)
    since = (local - exit_local).total_seconds() / 60.0
    quiet = 0 <= since < quiet_minutes
    if local >= exit_local:
        exit_local = datetime.combine(local.date() + timedelta(days=1), time(hh, mm), tzinfo=z)
    return exit_local.astimezone(ZoneInfo("UTC")), quiet
