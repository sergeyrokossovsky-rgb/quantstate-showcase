import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qs_range import (HarModel, QuantileHarModel, build_features, diebold_mariano, expected_calibration_error,  # noqa: E402
                      har_lags, interval_coverage, pinball, prob_exceed, qlike)
from qs_range.features import split  # noqa: E402
from qs_range.synthetic import make_market  # noqa: E402


@pytest.fixture(scope="module")
def market():
    ohlc, iv, ev = make_market(n_days=900, seed=3)
    return build_features(ohlc, iv, ev)


def test_har_lags_are_point_in_time():
    y = pd.Series(np.arange(1, 31, dtype=float))
    lag = har_lags(y)
    assert np.isnan(lag["d"].iloc[0]) and lag["d"].iloc[10] == 10.0          # only D-1 is visible at D
    assert lag["w"].iloc[10] == pytest.approx(np.mean([6, 7, 8, 9, 10]))
    assert np.isnan(lag["m"].iloc[10]) and not np.isnan(lag["m"].iloc[25])


def test_features_no_lookahead(market):
    f2 = market.copy()
    # changing the target of the last day must not change any feature of the last day
    ohlc, iv, ev = make_market(n_days=900, seed=3)
    ohlc.iloc[-1, ohlc.columns.get_loc("high")] *= 1.05
    g = build_features(ohlc, iv, ev)
    cols = ["ln_d", "ln_w", "ln_m", "ln_iv", "event", "med60"]
    pd.testing.assert_series_equal(g[cols].iloc[-1], f2[cols].iloc[-1])
    assert g["y"].iloc[-1] != f2["y"].iloc[-1]


def test_split_is_chronological(market):
    dev, val, test = split(market, "2020-12-31", "2021-12-31")
    assert dev.index.max() < val.index.min() and val.index.max() < test.index.min()


def test_quantiles_sorted_and_models_fit(market):
    dev, val, test = split(market, "2020-12-31", "2021-12-31")
    q = QuantileHarModel(["ln_iv", "abs_gap", "event"]).fit(dev).predict_log(test)
    assert (np.diff(q.values, axis=1) >= 0).all()
    f = HarModel(["ln_iv"]).fit(dev).predict(test)
    assert (f > 0).all() and len(f) > 100


def test_extra_information_helps_on_synthetic_data(market):
    dev, val, test = split(market, "2020-12-31", "2021-12-31")
    tr = pd.concat([dev, val])
    y = test.dropna(subset=["ln_d", "ln_w", "ln_m", "ln_iv"])["y"]
    base = HarModel().fit(tr).predict(test).loc[y.index]
    x = HarModel(["ln_iv", "event"]).fit(tr).predict(test).loc[y.index]
    assert qlike(y, x) < qlike(y, base)          # the synthetic market is built so that IV and events carry signal


def test_metrics():
    assert qlike([1, 2], [1, 2]) == pytest.approx(0.0)
    assert pinball([1.0], [0.0], 0.9) == pytest.approx(0.9) and pinball([0.0], [1.0], 0.9) == pytest.approx(0.1)
    assert interval_coverage([1, 2, 3], [0, 0, 0], [2, 2, 2]) == pytest.approx(2 / 3)
    t, p = diebold_mariano(np.zeros(100) + 0.1 * np.random.default_rng(1).normal(size=100), np.ones(100))
    assert t < 0 and p < 0.01
    assert expected_calibration_error([0.1, 0.9], [0, 1]) == pytest.approx(0.1)


def test_exceedance_monotone_and_consistent():
    taus = [0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
    q = [-5.0, -4.7, -4.5, -4.3, -4.0, -3.8]
    ps = [prob_exceed(q, taus, c) for c in np.linspace(-6, -3, 25)]
    assert all(a >= b - 1e-12 for a, b in zip(ps, ps[1:]))
    assert prob_exceed(q, taus, -4.5) == pytest.approx(0.5)
    assert prob_exceed(q, taus, -3.8) == pytest.approx(0.05)
