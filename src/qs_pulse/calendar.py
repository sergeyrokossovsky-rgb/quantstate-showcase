"""qs_pulse.calendar — NYSE trading calendar from rules (holidays, observed days, early closes).

Used by the public QS Pulse forecast to decide when a session is forecast at all: full sessions only,
early-close days are skipped because the model is trained on full sessions. Special closures (e.g. national
days of mourning) are listed explicitly. Author: Sergei Rokossovskii (QuantState LLC)."""
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

SPECIAL_CLOSED = {date(2025, 1, 9)}          # national day of mourning (President Carter)
SPECIAL_EARLY: set = set()


def _easter(y: int) -> date:
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(y, month, day)


def _nth_weekday(y: int, m: int, wd: int, n: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(wd - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(y: int, m: int, wd: int) -> date:
    d = date(y, m + 1, 1) - timedelta(days=1) if m < 12 else date(y, 12, 31)
    return d - timedelta(days=(d.weekday() - wd) % 7)


def _observed(d: date) -> Optional[date]:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


@lru_cache(maxsize=64)
def nyse_holidays(y: int) -> frozenset:
    hs = set()
    ny = date(y, 1, 1)
    if ny.weekday() == 6:
        hs.add(ny + timedelta(days=1))
    elif ny.weekday() != 5:                       # NYSE does not observe New Year on the prior Friday
        hs.add(ny)
    hs.add(_nth_weekday(y, 1, 0, 3))              # MLK
    hs.add(_nth_weekday(y, 2, 0, 3))              # Presidents
    hs.add(_easter(y) - timedelta(days=2))        # Good Friday
    hs.add(_last_weekday(y, 5, 0))                # Memorial
    if y >= 2022:
        hs.add(_observed(date(y, 6, 19)))         # Juneteenth
    hs.add(_observed(date(y, 7, 4)))
    hs.add(_nth_weekday(y, 9, 0, 1))              # Labor
    hs.add(_nth_weekday(y, 11, 3, 4))             # Thanksgiving
    hs.add(_observed(date(y, 12, 25)))
    return frozenset(hs | {d for d in SPECIAL_CLOSED if d.year == y})


@lru_cache(maxsize=64)
def nyse_early_closes(y: int) -> frozenset:
    out = set()
    j3 = date(y, 7, 3)
    if j3.weekday() < 5 and j3 not in nyse_holidays(y) and date(y, 7, 4).weekday() not in (5, 6, 0):
        out.add(j3)                               # July 3 when July 4 falls Tue–Fri
    out.add(_nth_weekday(y, 11, 3, 4) + timedelta(days=1))      # day after Thanksgiving
    c24 = date(y, 12, 24)
    if c24.weekday() < 5 and c24 not in nyse_holidays(y):
        out.add(c24)
    return frozenset(out | {d for d in SPECIAL_EARLY if d.year == y})


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in nyse_holidays(d.year)


def is_full_day(d: date) -> bool:
    return is_trading_day(d) and d not in nyse_early_closes(d.year)


def prev_trading_day(d: date) -> date:
    d -= timedelta(days=1)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def next_trading_day(d: date) -> date:
    d += timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d
