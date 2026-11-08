"""Point-in-time feature construction for a daily range forecast.

Every feature for session D uses information available before the forecast time:
closes up to D-1, the implied-volatility index close of D-1, and (optionally) the opening gap of D.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd


def log_range(df: pd.DataFrame) -> pd.Series:
    """ln(High / Low) of each session — a scale-free daily range."""
    return np.log(df["high"] / df["low"])


def har_lags(y: pd.Series) -> pd.DataFrame:
    """HAR(1, 5, 22) lags of a positive series (Corsi, 2009), shifted so row D only sees D-1 and earlier."""
    lagged = y.shift(1)
    return pd.DataFrame({
        "d": lagged,
        "w": lagged.rolling(5, min_periods=4).mean(),
        "m": lagged.rolling(22, min_periods=18).mean(),
    }, index=y.index)


def build_features(ohlc: pd.DataFrame, iv: Optional[pd.Series] = None, events: Optional[pd.Index] = None) -> pd.DataFrame:
    """Daily OHLC (+ optional implied-vol index in % points, + optional event dates) → model frame.

    Columns: y (target, log range), ln_d / ln_w / ln_m (HAR lags in logs), ln_iv (ln daily sigma implied by the
    index of D-1), abs_gap (|ln open_D / close_D-1|), event (1 on listed dates), med60 (median range of the
    previous 60 sessions, used to express "strong day" thresholds).
    """
    df = ohlc.sort_index().copy()
    y = log_range(df)
    lags = har_lags(y)
    out = pd.DataFrame(index=df.index)
    out["y"] = y
    for k in ("d", "w", "m"):
        out[f"ln_{k}"] = np.log(lags[k])
    out["abs_gap"] = np.log(df["open"] / df["close"].shift(1)).abs()
    if iv is not None:
        iv_prev = iv.reindex(df.index).ffill().shift(1)
        out["ln_iv"] = np.log(iv_prev / 100.0 / math.sqrt(252.0))
    out["event"] = df.index.isin(events).astype(float) if events is not None else 0.0
    out["med60"] = y.shift(1).rolling(60, min_periods=40).median()
    return out


def split(frame: pd.DataFrame, dev_end: str, val_end: str):
    """Chronological DEV / VAL / TEST split (no shuffling, no overlap)."""
    dev = frame.loc[:dev_end]
    val = frame.loc[pd.Timestamp(dev_end) + pd.Timedelta(days=1):val_end]
    test = frame.loc[pd.Timestamp(val_end) + pd.Timedelta(days=1):]
    return dev, val, test
