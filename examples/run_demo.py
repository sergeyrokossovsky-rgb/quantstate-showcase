"""End-to-end demo of the forecasting protocol.

    python examples/run_demo.py                       # synthetic market (offline)
    python examples/run_demo.py --ohlc SPY.csv --iv VIX_History.csv
        SPY.csv: date,open,high,low,close (any daily source you are licensed to use)
        VIX_History.csv: the public Cboe file (DATE,OPEN,HIGH,LOW,CLOSE)

Protocol: baselines first; model parameters on DEV for VAL and on DEV+VAL for TEST; the TEST block is scored
once and reported against acceptance criteria fixed in advance.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qs_range import (HarModel, QuantileHarModel, build_features, diebold_mariano, implied_vol_baseline,  # noqa: E402
                      interval_coverage, pinball, prob_exceed, qlike)
from qs_range.features import split  # noqa: E402
from qs_range.synthetic import make_market  # noqa: E402

EXTRAS = ["ln_iv", "abs_gap", "event"]
ACCEPT = {"qlike_gain": 0.03, "dm_p": 0.10, "pinball_gain": 0.05, "coverage": (0.76, 0.84)}


def load(args):
    if not args.ohlc:
        return make_market()
    o = pd.read_csv(args.ohlc, parse_dates=[0], index_col=0)
    o.columns = [c.lower() for c in o.columns]
    iv = pd.read_csv(args.iv, parse_dates=["DATE"]).set_index("DATE")["CLOSE"]
    return o[["open", "high", "low", "close"]], iv, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ohlc")
    ap.add_argument("--iv")
    ap.add_argument("--dev-end", default="2022-12-31")
    ap.add_argument("--val-end", default="2023-12-31")
    args = ap.parse_args()
    ohlc, iv, events = load(args)
    fr = build_features(ohlc, iv, events)
    dev, val, test = split(fr, args.dev_end, args.val_end)
    train = pd.concat([dev, val])

    har = HarModel().fit(train)
    harx = HarModel(EXTRAS).fit(train)
    f_har, f_x = har.predict(test), harx.predict(test)
    common = f_har.index.intersection(f_x.index)
    y = test.loc[common, "y"]
    l_har, l_x = qlike(y, f_har[common]), qlike(y, f_x[common])
    r = y / f_x[common]
    rb = y / f_har[common]
    t, p = diebold_mariano(r - np.log(r) - 1, rb - np.log(rb) - 1)
    f_iv = implied_vol_baseline(train, test.loc[common])

    qm = QuantileHarModel(EXTRAS).fit(train)
    Q = qm.predict_log(test).loc[common]
    yl = np.log(y)
    taus = list(qm.taus)
    pin_m = np.mean([pinball(yl, Q.iloc[:, i], tau) for i, tau in enumerate(taus)])
    resid = np.log(train["y"]) - np.log(har.predict(train))
    qs = np.quantile(resid.dropna(), taus)
    Qb = np.log(f_har[common]).values[:, None] + qs[None, :]
    pin_b = np.mean([pinball(yl, Qb[:, i], tau) for i, tau in enumerate(taus)])
    cov = interval_coverage(yl, Q["q10"], Q["q90"])

    print(f"TEST days: {len(common)}")
    print(f"QLIKE  HAR {l_har:.4f} | IV-baseline {qlike(y, f_iv):.4f} | HAR-X {l_x:.4f} | DM t={t:.2f} p={p:.4f}")
    print(f"Pinball HAR-residual quantiles {pin_b:.5f} | quantile HAR-X {pin_m:.5f} | 80% interval coverage {cov:.3f}")
    ok_vol = (1 - l_x / l_har) >= ACCEPT["qlike_gain"] and p < ACCEPT["dm_p"]
    ok_rng = (1 - pin_m / pin_b) >= ACCEPT["pinball_gain"] and ACCEPT["coverage"][0] <= cov <= ACCEPT["coverage"][1]
    print(f"Acceptance — volatility model: {'PASS' if ok_vol else 'FAIL'} · range quantiles: {'PASS' if ok_rng else 'FAIL'}")
    last = Q.iloc[-1].values
    med = test["med60"].iloc[-1]
    print(f"Last day: median range {100 * np.exp(last[2]):.2f}% · P(range > 1.5×median60) "
          f"{prob_exceed(last, taus, float(np.log(1.5 * med))):.2f}")


if __name__ == "__main__":
    main()
