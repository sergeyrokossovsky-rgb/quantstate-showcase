"""HAR-X (OLS in logs) and quantile HAR-X models + an implied-volatility baseline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd
import statsmodels.api as sm

HAR = ["ln_d", "ln_w", "ln_m"]


def _design(frame: pd.DataFrame, extras: Sequence[str]) -> pd.DataFrame:
    X = frame[HAR + list(extras)].copy()
    X.insert(0, "const", 1.0)
    return X


def _clean(frame: pd.DataFrame, extras: Sequence[str]) -> pd.DataFrame:
    cols = HAR + list(extras) + ["y"]
    f = frame.dropna(subset=cols)
    return f[np.isfinite(f[cols]).all(axis=1) & (f["y"] > 0)]


@dataclass
class HarModel:
    """ln y_D = b0 + bd ln y_{D-1} + bw ln mean5 + bm ln mean22 (+ extras). Level forecast with log-normal bias correction."""
    extras: List[str] = field(default_factory=list)
    params_: pd.Series = None
    sigma2_: float = 0.0

    def fit(self, frame: pd.DataFrame) -> "HarModel":
        f = _clean(frame, self.extras)
        X = _design(f, self.extras)
        res = sm.OLS(np.log(f["y"]), X).fit()
        self.params_ = res.params
        self.sigma2_ = float(np.var(res.resid, ddof=X.shape[1]))
        return self

    def predict(self, frame: pd.DataFrame) -> pd.Series:
        f = _clean(frame, self.extras)
        mu = _design(f, self.extras) @ self.params_
        return np.exp(mu + self.sigma2_ / 2.0)


@dataclass
class QuantileHarModel:
    """Linear quantile regression of ln y on the HAR(-X) design; quantiles are sorted to avoid crossing."""
    extras: List[str] = field(default_factory=list)
    taus: Sequence[float] = (0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
    params_: Dict[float, pd.Series] = field(default_factory=dict)

    def fit(self, frame: pd.DataFrame) -> "QuantileHarModel":
        f = _clean(frame, self.extras)
        X, y = _design(f, self.extras), np.log(f["y"])
        self.params_ = {t: sm.QuantReg(y, X).fit(q=t, max_iter=5000).params for t in self.taus}
        return self

    def predict_log(self, frame: pd.DataFrame) -> pd.DataFrame:
        f = _clean(frame, self.extras)
        X = _design(f, self.extras)
        q = np.column_stack([X @ self.params_[t] for t in self.taus])
        q.sort(axis=1)
        return pd.DataFrame(q, index=f.index, columns=[f"q{int(round(100 * t)):02d}" for t in self.taus])


def implied_vol_baseline(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
    """range ≈ k · sigma_implied, k estimated on the training window (geometric mean ratio)."""
    tr = train.dropna(subset=["y", "ln_iv"])
    k = float(np.exp(np.mean(np.log(tr["y"]) - tr["ln_iv"])))
    return k * np.exp(test["ln_iv"])
