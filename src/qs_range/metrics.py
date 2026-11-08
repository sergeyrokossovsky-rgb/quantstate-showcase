"""Forecast evaluation: volatility loss, quantile loss, interval coverage, DM test, probability calibration."""
from __future__ import annotations

import math
from typing import Sequence, Tuple

import numpy as np
from scipy import stats


def qlike(y: Sequence[float], f: Sequence[float]) -> float:
    """QLIKE loss for a positive volatility / variance proxy (Patton, 2011). Lower is better."""
    r = np.asarray(y, float) / np.asarray(f, float)
    return float(np.mean(r - np.log(r) - 1.0))


def pinball(y: Sequence[float], q: Sequence[float], tau: float) -> float:
    """Quantile (pinball) loss at level tau."""
    u = np.asarray(y, float) - np.asarray(q, float)
    return float(np.mean(np.maximum(tau * u, (tau - 1.0) * u)))


def interval_coverage(y, lo, hi) -> float:
    y, lo, hi = (np.asarray(a, float) for a in (y, lo, hi))
    return float(np.mean((y >= lo) & (y <= hi)))


def diebold_mariano(loss_a, loss_b, lag: int = 5) -> Tuple[float, float]:
    """DM statistic with a Newey–West variance. Returns (t, one-sided p for 'A has lower loss than B')."""
    d = np.asarray(loss_a, float) - np.asarray(loss_b, float)
    n, mu = len(d), float(np.mean(d))
    s = float(np.var(d))
    for k in range(1, lag + 1):
        s += 2.0 * (1.0 - k / (lag + 1.0)) * float(np.mean((d[k:] - mu) * (d[:-k] - mu)))
    t = mu / math.sqrt(s / n) if s > 0 else 0.0
    return t, float(stats.norm.cdf(t))


def brier_skill(p, y, base_rate: float) -> float:
    """1 − Brier(p) / Brier(climatology). > 0 means better than always forecasting the base rate."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    b, bc = np.mean((p - y) ** 2), np.mean((base_rate - y) ** 2)
    return float(1.0 - b / bc) if bc > 0 else float("nan")


def expected_calibration_error(p, y, bins: int = 10) -> float:
    p, y = np.asarray(p, float), np.asarray(y, float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    e = 0.0
    for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
        m = (p >= a) & ((p < b) if i < bins - 1 else (p <= b))
        if m.any():
            e += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(e)
