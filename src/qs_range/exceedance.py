"""Exceedance probabilities from a set of predicted quantiles.

Probabilities are read off the SAME conditional distribution as the quantiles (no separate classifier), so
P(range > big) ≤ P(range > moderate) always holds. Inside the quantile grid the CDF is interpolated linearly;
beyond the outer quantiles the tails are log-linear.
"""
from __future__ import annotations

import math
from typing import Sequence


def prob_exceed(q: Sequence[float], taus: Sequence[float], c: float) -> float:
    q, t = list(q), list(taus)
    if c <= q[0]:
        return 1.0 - t[0] * math.exp(-(q[0] - c) / max(1e-9, q[1] - q[0]) * math.log(t[1] / t[0]))
    if c >= q[-1]:
        lam = math.log((1.0 - t[-2]) / (1.0 - t[-1])) / max(1e-9, q[-1] - q[-2])
        return (1.0 - t[-1]) * math.exp(-lam * (c - q[-1]))
    for j in range(len(q) - 1):
        if q[j] <= c <= q[j + 1]:
            F = t[j] + (t[j + 1] - t[j]) * (c - q[j]) / max(1e-12, q[j + 1] - q[j])
            return 1.0 - F
    return 0.5
