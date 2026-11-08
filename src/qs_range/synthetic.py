"""Synthetic daily OHLC with clustered volatility + a noisy implied-vol index, for offline demos and tests."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def make_market(n_days: int = 1500, seed: int = 7, start: str = "2019-01-02") -> tuple[pd.DataFrame, pd.Series, pd.Index]:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n_days)
    # log-variance follows an AR(1) with occasional shocks → volatility clustering
    lv = np.empty(n_days)
    lv[0] = math.log(0.011 ** 2)
    for i in range(1, n_days):
        shock = rng.normal(0, 0.35) + (1.6 if rng.random() < 0.01 else 0.0)
        lv[i] = 0.97 * lv[i - 1] + 0.03 * math.log(0.011 ** 2) + shock * 0.25
    sig = np.exp(lv / 2)
    events = idx[rng.random(n_days) < 0.07]
    sig = sig * np.where(idx.isin(events), 1.25, 1.0)
    close = 4000.0 * np.exp(np.cumsum(rng.normal(0, sig)))
    prev = np.r_[close[0], close[:-1]]
    gap = rng.normal(0, 0.35 * sig)
    open_ = prev * np.exp(gap)
    # Brownian-bridge-ish range: E[ln(H/L)] ≈ 1.6 σ
    rng_len = sig * (1.6 + 0.5 * rng.standard_normal(n_days)).clip(0.4)
    hi = np.maximum(open_, close) * np.exp(rng_len * rng.uniform(0.2, 0.8, n_days))
    lo = np.minimum(open_, close) * np.exp(-rng_len * rng.uniform(0.2, 0.8, n_days))
    ohlc = pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close}, index=idx)
    # implied vol: annualised sigma in % points with a premium and noise
    iv = pd.Series(100 * sig * math.sqrt(252) * 1.15 * np.exp(rng.normal(0, 0.12, n_days)), index=idx, name="iv")
    return ohlc, iv, events
