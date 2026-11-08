"""qs_range — daily range / realised-volatility forecasting toolkit (portfolio sample).

Public, textbook building blocks (HAR models, linear quantile regression, forecast evaluation) packaged the way
they are used in production research: strict point-in-time features, chronological DEV / VAL / TEST split,
baselines first, and acceptance criteria fixed before the test set is opened.

Author: Sergei Rokossovskii (QuantState LLC). This sample contains no proprietary trading logic or data.
"""
from .features import build_features, har_lags
from .models import HarModel, QuantileHarModel, implied_vol_baseline
from .metrics import qlike, pinball, interval_coverage, diebold_mariano, brier_skill, expected_calibration_error
from .exceedance import prob_exceed

__all__ = [
    "build_features", "har_lags", "HarModel", "QuantileHarModel", "implied_vol_baseline",
    "qlike", "pinball", "interval_coverage", "diebold_mariano", "brier_skill", "expected_calibration_error",
    "prob_exceed",
]
__version__ = "1.0.0"
