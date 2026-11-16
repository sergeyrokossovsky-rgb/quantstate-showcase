"""qs_pulse.record — grading a published interval forecast and summarising a trade record in ticks.

* grade(): a forecast band fixed before the session is compared with the realised range after the close;
  nothing is edited afterwards, misses stay in the ledger.
* metrics(): weekly / since-start statistics of a trade record in ticks per contract after round-turn costs —
  the unit lets anyone rescale to their own size. Author: Sergei Rokossovskii (QuantState LLC)."""
import math
from typing import Dict, List, Optional


def range_pct(high: float, low: float) -> float:
    """Session range as 100·ln(High/Low)."""
    if not (high > low > 0):
        raise ValueError("high must exceed low > 0")
    return 100.0 * math.log(high / low)


def grade(q_low: float, q_high: float, actual: float) -> str:
    return "inside" if q_low <= actual <= q_high else ("above" if actual > q_high else "below")


def coverage(verdicts: List[str]) -> Optional[float]:
    return sum(v == "inside" for v in verdicts) / len(verdicts) if verdicts else None


def trade_ticks(entry: float, exit_: float, side: str, tick: float, cost_ticks: float = 0.5) -> float:
    s = 1 if side.lower().startswith("l") else -1
    return round((exit_ - entry) / tick * s, 2) - cost_ticks


def metrics(t: List[float]) -> Dict[str, Optional[float]]:
    wins, losses = [v for v in t if v > 0], [v for v in t if v < 0]
    eq = peak = dd = 0.0
    for v in t:
        eq += v
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    aw = sum(wins) / len(wins) if wins else 0.0
    al = sum(losses) / len(losses) if losses else 0.0
    return {"trades": len(t), "net": round(sum(t), 1), "win_rate": round(len(wins) / len(t), 4) if t else None,
            "avg_win": round(aw, 1), "avg_loss": round(al, 1), "rr": round(aw / abs(al), 2) if al else None,
            "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses else None,
            "per_trade": round(sum(t) / len(t), 2) if t else None, "max_dd": round(dd, 1)}


def sharpe_daily(daily: List[float], min_days: int = 20) -> Optional[float]:
    """Annualised Sharpe of daily P&L in ticks — reported only with at least `min_days` trading days."""
    if len(daily) < min_days:
        return None
    mu = sum(daily) / len(daily)
    sd = math.sqrt(sum((x - mu) ** 2 for x in daily) / (len(daily) - 1))
    return round(mu / sd * math.sqrt(252), 2) if sd > 0 else None
