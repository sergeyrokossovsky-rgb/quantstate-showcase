import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qs_range.intraday import NextHourModel, forward, rv_windows  # noqa: E402


def _market(days=120, seed=4):
    rng = np.random.default_rng(seed)
    n = days * 390
    hour = np.tile(np.repeat(np.arange(7), [60, 60, 60, 60, 60, 60, 30]), days)[:n]
    diurnal = np.where(hour == 0, 1.8, np.where(hour == 6, 1.4, 1.0))
    vol = np.exp(np.cumsum(rng.normal(0, 0.01, n)) * 0.3) * 4e-4 * diurnal       # persistent + U-shaped
    r = pd.Series(rng.normal(0, vol))
    px = 5000 * np.exp(r.cumsum())
    high, low = px * (1 + vol * 0.5), px * (1 - vol * 0.5)
    return r, pd.Series(high), pd.Series(low), pd.Series(hour), pd.Series(np.arange(n) % 390)


def qlike(y, f):
    ok = (y > 0) & (f > 0)
    return float(np.mean(y[ok] / f[ok] - np.log(y[ok] / f[ok]) - 1))


def test_next_hour_beats_constant_and_is_calibrated():
    r, hi, lo, hour, slot = _market()
    feat, y = rv_windows(r), forward(r, hi, lo)
    cut = len(r) // 2
    m = NextHourModel().fit(feat.iloc[:cut], hour.iloc[:cut], y.iloc[:cut], slot.iloc[:cut])
    p = m.predict(feat.iloc[cut:], hour.iloc[cut:])
    yt = y.iloc[cut:]
    ok = p["rv60"].notna() & yt["y_rv"].notna()
    const = np.full(ok.sum(), y.iloc[:cut]["y_rv"].mean())
    assert qlike(yt.loc[ok, "y_rv"].values, p.loc[ok, "rv60"].values) < 0.8 * qlike(yt.loc[ok, "y_rv"].values, const)
    cov = ((yt.loc[ok, "y_rg"] >= p.loc[ok, "rg_q10"]) & (yt.loc[ok, "y_rg"] <= p.loc[ok, "rg_q90"])).mean()
    assert 0.72 <= cov <= 0.88
    assert 0 <= m.live_index(float(p["rv60"].dropna().iloc[-1]), 200) <= 100


def test_targets_do_not_overlap_features():
    r = pd.Series(np.arange(1, 200, dtype=float) * 1e-4)
    f, y = rv_windows(r), forward(r, r + 1, r + 0.5)
    # forward window at t starts at t+1: changing r[t] must not change y_rv[t]
    r2 = r.copy(); r2.iloc[100] = 0.5
    assert forward(r2, r2 + 1, r2 + 0.5)["y_rv"].iloc[100] == y["y_rv"].iloc[100]
