from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

LAG_COLS = ("lag_max_s", "lag_s", "lag_last_s")


@dataclass
class Episode:
    symbol: str
    start: pd.Timestamp
    end: pd.Timestamp
    peak_s: float
    growth_s_per_min: float
    windows: int
    verdict: str = "unknown"
    others: Dict[str, float] = field(default_factory=dict)   # share of elevated windows per other symbol

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60.0


def load_csv(paths: Iterable[str | Path]) -> pd.DataFrame:
    """Concatenate monitor CSVs → columns utc (UTC timestamp), symbol, lag (s)."""
    frames = []
    for p in paths:
        d = pd.read_csv(p)
        tcol = "utc" if "utc" in d.columns else "utc_pc"
        lcol = next(c for c in LAG_COLS if c in d.columns)
        frames.append(pd.DataFrame({"utc": pd.to_datetime(d[tcol], utc=True), "symbol": d["symbol"].astype(str),
                                    "lag": pd.to_numeric(d[lcol], errors="coerce")}))
    out = pd.concat(frames, ignore_index=True).dropna(subset=["lag"])
    return out.sort_values(["symbol", "utc"]).reset_index(drop=True)


def find_episodes(df: pd.DataFrame, threshold_s: float = 5.0, min_windows: int = 2, max_gap_windows: int = 1,
                  window_s: float = 10.0) -> List[Episode]:
    """Runs of windows with lag ≥ threshold (a single clean window inside a run is tolerated)."""
    eps: List[Episode] = []
    for sym, g in df.groupby("symbol", sort=True):
        g = g.sort_values("utc")
        t, lag = g["utc"].to_numpy(), g["lag"].to_numpy(dtype=float)
        bad = lag >= threshold_s
        i, n = 0, len(g)
        while i < n:
            if not bad[i]:
                i += 1
                continue
            j, last_bad, gap = i, i, 0
            while j + 1 < n:
                step = (pd.Timestamp(t[j + 1]) - pd.Timestamp(t[j])).total_seconds()
                if step > window_s * (max_gap_windows + 1.5):          # recording hole → end of run
                    break
                j += 1
                if bad[j]:
                    last_bad, gap = j, 0
                else:
                    gap += 1
                    if gap > max_gap_windows:
                        break
            k = np.arange(i, last_bad + 1)
            k = k[bad[k]]
            if len(k) >= min_windows:
                mins = (pd.to_datetime(t[k]) - pd.Timestamp(t[i])).total_seconds().to_numpy() / 60.0
                slope = float(np.polyfit(mins, lag[k], 1)[0]) if len(k) >= 3 and np.ptp(mins) > 0 else float("nan")
                eps.append(Episode(sym, pd.Timestamp(t[i]), pd.Timestamp(t[last_bad]), float(lag[k].max()), slope, len(k)))
            i = last_bad + 1
    return eps


def classify(eps: List[Episode], df: pd.DataFrame, threshold_s: float = 5.0, pad_s: float = 30.0,
             shared_share: float = 0.5, local_share: float = 0.2) -> List[Episode]:
    """Label each episode by the share of elevated windows of every other symbol inside [start − pad, end + pad]."""
    for e in eps:
        a, b = e.start - pd.Timedelta(seconds=pad_s), e.end + pd.Timedelta(seconds=pad_s)
        shares: Dict[str, float] = {}
        for sym, g in df[df["symbol"] != e.symbol].groupby("symbol"):
            w = g[(g["utc"] >= a) & (g["utc"] <= b)]
            if len(w):
                shares[sym] = round(float((w["lag"] >= threshold_s).mean()), 3)
        e.others = shares
        if not shares:
            e.verdict = "unknown"
        elif max(shares.values()) >= shared_share:
            e.verdict = "shared"
        elif max(shares.values()) <= local_share:
            e.verdict = "local"
        else:
            e.verdict = "mixed"
    return eps


def summary(eps: List[Episode]) -> str:
    if not eps:
        return "no lag episodes"
    lines = []
    for e in sorted(eps, key=lambda x: x.start):
        g = "—" if np.isnan(e.growth_s_per_min) else f"{e.growth_s_per_min:+.0f} s/min"
        oth = ", ".join(f"{k} {100 * v:.0f}%" for k, v in sorted(e.others.items())) or "no other data"
        lines.append(f"{e.start:%Y-%m-%d %H:%M:%S}Z {e.symbol:<4} {e.minutes:5.1f} min peak {e.peak_s:6.1f} s growth {g:>10} "
                     f"→ {e.verdict.upper():<7} (others elevated: {oth})")
    v = pd.Series([e.verdict for e in eps]).value_counts().to_dict()
    lines.append("verdicts: " + ", ".join(f"{k}={n}" for k, n in v.items()))
    return "\n".join(lines)


if __name__ == "__main__":   # python -m qs_feedlag.episodes feedlag_*.csv
    import sys

    data = load_csv(sys.argv[1:])
    print(summary(classify(find_episodes(data), data)))
