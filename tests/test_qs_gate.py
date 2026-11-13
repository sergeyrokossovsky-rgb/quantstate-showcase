import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qs_gate import PermissionWindow, next_deadline  # noqa: E402

T0 = datetime(2026, 11, 13, 14, 0, tzinfo=timezone.utc)


def _run(scores, w):
    opened = []
    for i, sc in enumerate(scores):
        if w.on_bar_close(sc, T0 + timedelta(minutes=i + 1)):
            opened.append(i)
    return opened


def test_window_opens_once_per_excursion_and_rearms():
    w = PermissionWindow(60, timedelta(minutes=60), max_uses=2, rearm_bars=3)
    opened = _run([50, 65, 70, 55, 66, 40, 40, 40, 61], w)
    assert opened == [1, 8]                       # 66 at i=4 does not re-open: only 1 bar below before it


def test_uses_counted_on_fill_and_capped():
    w = PermissionWindow(60, timedelta(minutes=30), max_uses=2, rearm_bars=30)
    w.on_bar_close(70, T0)
    now = T0 + timedelta(minutes=5)
    assert w.allows(now) == (True, "")
    w.book_fill(1); w.book_fill(1)
    assert w.allows(now) == (False, "max_uses")
    w.book_fill(0)                                # stale id ignored
    assert w.s.uses == 2
    assert w.allows(T0 + timedelta(minutes=31)) == (False, "wait")


def test_missing_score_counts_as_below():
    w = PermissionWindow(30, timedelta(minutes=60), rearm_bars=2)
    w.on_bar_close(35, T0)
    w.on_bar_close(None, T0 + timedelta(minutes=1))
    w.on_bar_close(None, T0 + timedelta(minutes=2))
    assert w.s.armed


def test_deadline_dst_and_quiet_period():
    # 13 Nov 2026 (CST, UTC−6): 14:00 CT → deadline today 15:00 CT = 21:00 UTC
    d, q = next_deadline(datetime(2026, 11, 13, 20, 0, tzinfo=timezone.utc), 1500)
    assert d == datetime(2026, 11, 13, 21, 0, tzinfo=timezone.utc) and not q
    # 15:05 CT → tomorrow, inside the quiet hour
    d, q = next_deadline(datetime(2026, 11, 13, 21, 5, tzinfo=timezone.utc), 1500)
    assert d == datetime(2026, 11, 14, 21, 0, tzinfo=timezone.utc) and q
    # overnight entry 17:30 CT in July (CDT, UTC−5) → 08:30 CT next day = 13:30 UTC
    d, _ = next_deadline(datetime(2026, 7, 1, 22, 30, tzinfo=timezone.utc), 830)
    assert d == datetime(2026, 7, 2, 13, 30, tzinfo=timezone.utc)
    assert next_deadline(datetime(2026, 7, 1, tzinfo=timezone.utc), 0) == (None, False)
