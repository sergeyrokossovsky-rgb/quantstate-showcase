"""Intraday next-hour volatility and range forecast (portfolio sample, synthetic data in tests).

Textbook intraday HAR: ln RV(t, t+60) = a + b5·ln RV(last 5 min) + b30·ln RV(last 30 min) + b60·ln RV(last 60 min)
+ hour-of-session effects, OLS with a log-normal bias correction. The price range of the next hour is modelled on the
same features (log of ln(H/L)) with empirical residual quantiles, because the range needed for stops/targets is not
a fixed multiple of the realised variance at a one-minute sampling grid.

A "live index" is the percentile of the forecast among historical forecasts issued at the same time of day — a level
measure. (A ratio "realised so far / expected so far" removes the level and ranks the next hour worse than plain VIX;
we keep it only as a caption.)

Author: Sergei Rokossovskii (QuantState LLC). No proprietary coefficients, data or trading logic."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Sequence

import numpy as np
import pandas as pd


def rv_windows(r: pd.Series, windows: Sequence[int] = (5, 30, 60)) -> pd.DataFrame:
    """Sums of squared one-minute log returns over trailing windows (≥ 80% of the window present)."""
    r2 = r ** 2
    return pd.DataFrame({f"l{w}": r2.rolling(w, min_periods=int(0.8 * w)).sum() for w in windows})


def forward(r: pd.Series, high: pd.Series, low: pd.Series, h: int = 60) -> pd.DataFrame:
    """Targets: RV of the next h returns and ln(max high / min low) of the next h bars (no overlap with features)."""
    r2 = r ** 2
    y_rv = r2[::-1].rolling(h, min_periods=int(0.8 * h)).sum()[::-1].shift(-1)
    hi = high[::-1].rolling(h, min_periods=int(0.8 * h)).max()[::-1].shift(-1)
    lo = low[::-1].rolling(h, min_periods=int(0.8 * h)).min()[::-1].shift(-1)
    return pd.DataFrame({"y_rv": y_rv, "y_rg": np.log(hi / lo)})


def _design(feat: pd.DataFrame, hour: pd.Series) -> pd.DataFrame:
    X = np.log(feat.where(feat > 0)).assign(c=1.0)
    H = pd.get_dummies(hour.astype(int), prefix="h", drop_first=True).astype(float)
    return pd.concat([X[["c"] + [c for c in X.columns if c != "c"]], H], axis=1)


@dataclass
class NextHourModel:
    coef_rv: pd.Series = field(default=None)
    coef_rg: pd.Series = field(default=None)
    bias: float = 1.0
    resid_q: np.ndarray = field(default=None)
    ref: Dict[int, np.ndarray] = field(default_factory=dict)

    def fit(self, feat: pd.DataFrame, hour: pd.Series, y: pd.DataFrame, slot: pd.Series) -> "NextHourModel":
        X = _design(feat, hour)
        ok = X.notna().all(axis=1) & (y["y_rv"] > 0) & (y["y_rg"] > 0)
        A = X[ok].values
        self.coef_rv = pd.Series(np.linalg.lstsq(A, np.log(y.loc[ok, "y_rv"]).values, rcond=None)[0], index=X.columns)
        res = np.log(y.loc[ok, "y_rv"]).values - A @ self.coef_rv.values
        self.bias = float(np.mean(np.exp(res)))
        self.coef_rg = pd.Series(np.linalg.lstsq(A, np.log(y.loc[ok, "y_rg"]).values, rcond=None)[0], index=X.columns)
        self.resid_q = np.quantile(np.log(y.loc[ok, "y_rg"]).values - A @ self.coef_rg.values, [0.1, 0.5, 0.9])
        f = np.exp(A @ self.coef_rv.values) * self.bias
        self.ref = {int(k): np.sort(v) for k, v in pd.Series(f, index=slot[ok].values).groupby(level=0)}
        return self

    def predict(self, feat: pd.DataFrame, hour: pd.Series) -> pd.DataFrame:
        X = _design(feat, hour).reindex(columns=self.coef_rv.index, fill_value=0.0)
        rv = np.exp(X.values @ self.coef_rv.values) * self.bias
        lr = X.values @ self.coef_rg.values
        q = np.exp(lr[:, None] + self.resid_q[None, :])
        return pd.DataFrame({"rv60": rv, "rg_q10": q[:, 0], "rg_q50": q[:, 1], "rg_q90": q[:, 2]}, index=feat.index)

    def live_index(self, rv60: float, slot: int) -> float:
        """Percentile (0–100) of a forecast among historical forecasts at the same time-of-day slot."""
        ref = self.ref[min(self.ref, key=lambda k: abs(k - slot))]
        return float(100.0 * np.searchsorted(ref, rv60) / len(ref))
