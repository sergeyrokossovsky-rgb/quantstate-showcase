import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qs_feedlag import classify, find_episodes, load_csv, summary  # noqa: E402


def _series(sym, start, n, lag_fn):
    t = pd.date_range(start, periods=n, freq="10s", tz="UTC")
    return pd.DataFrame({"utc": t, "symbol": sym, "lag": [lag_fn(i) for i in range(n)]})


def _frame():
    # 60 min of 10-s windows. ES: local backlog 20–30 min (grows 40 s/min). All three: shared spike 45–48 min.
    def es(i):
        m = i / 6
        if 20 <= m < 30:
            return 0.5 + 40 * (m - 20)
        return 0.5 + (12.0 if 45 <= m < 48 else 0.0)

    def other(i):
        m = i / 6
        return 0.4 + (12.0 if 45 <= m < 48 else 0.0)

    return pd.concat([_series("ES", "2026-11-09 19:00", 360, es), _series("NQ", "2026-11-09 19:00", 360, other),
                      _series("RTY", "2026-11-09 19:00", 360, other)], ignore_index=True)


def test_local_backlog_and_shared_spike():
    df = _frame()
    eps = classify(find_episodes(df), df)
    es = sorted([e for e in eps if e.symbol == "ES"], key=lambda e: e.start)
    assert len(es) == 2
    assert es[0].verdict == "local" and es[0].peak_s > 350 and 35 < es[0].growth_s_per_min < 45
    assert es[1].verdict == "shared" and es[1].others["NQ"] >= 0.5
    assert {e.verdict for e in eps if e.symbol != "ES"} == {"shared"}
    assert "LOCAL" in summary(eps) and "verdicts:" in summary(eps)


def test_single_spike_is_not_an_episode_and_hole_splits():
    df = _series("ES", "2026-11-09 19:00", 30, lambda i: 9.0 if i == 10 else 0.3)
    assert find_episodes(df) == []
    a = _series("ES", "2026-11-09 19:00", 5, lambda i: 9.0)
    b = _series("ES", "2026-11-09 19:10", 5, lambda i: 9.0)            # 10-min recording hole
    assert len(find_episodes(pd.concat([a, b], ignore_index=True))) == 2


def test_load_csv_both_formats(tmp_path):
    p1 = tmp_path / "a.csv"
    p1.write_text("utc,symbol,trades,lag_s,lag_max_s,raw_s,div_t,gap_max_ms\n2026-11-09T19:00:00Z,ES,10,0.4,0.6,1.0,0,12\n")
    p2 = tmp_path / "b.csv"
    p2.write_text("utc_pc,symbol,window_s,trades,quotes,lag_last_s,lag_max_s\n2026-11-09T19:00:00.000Z,NQ,10,5,9,0.3,0.5\n")
    d = load_csv([p1, p2])
    assert list(d["symbol"]) == ["ES", "NQ"] and np.allclose(d["lag"], [0.6, 0.5])
