import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qs_pulse import (coverage, grade, is_full_day, metrics, next_trading_day, nyse_early_closes, nyse_holidays,  # noqa: E402
                      range_pct, sharpe_daily, trade_ticks)


def test_calendar():
    assert date(2026, 7, 3) in nyse_holidays(2026) and date(2025, 1, 9) in nyse_holidays(2025)
    assert nyse_early_closes(2026) == {date(2026, 11, 27), date(2026, 12, 24)}
    assert next_trading_day(date(2026, 11, 25)) == date(2026, 11, 27) and not is_full_day(date(2026, 11, 27))


def test_grade_and_coverage():
    a = range_pct(101.0, 100.0)
    assert abs(a - 100 * math.log(1.01)) < 1e-12
    assert grade(0.5, 1.5, a) == "inside" and grade(0.5, 0.9, a) == "above" and grade(1.2, 2.0, a) == "below"
    assert coverage(["inside"] * 4 + ["above"]) == 0.8


def test_record_metrics():
    t = [trade_ticks(7600, 7612, "Long", 0.25), trade_ticks(7600, 7603.5, "Short", 0.25), trade_ticks(7650, 7640, "Short", 0.25)]
    assert t == [47.5, -14.5, 39.5]
    m = metrics(t)
    assert m["trades"] == 3 and m["net"] == 72.5 and m["max_dd"] == -14.5 and m["profit_factor"] == round(87 / 14.5, 2)
    assert sharpe_daily([1.0] * 5) is None
