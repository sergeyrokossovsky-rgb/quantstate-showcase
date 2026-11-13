# Research lab

≈ 30 000 lines of Python research code and ≈ 360 written protocols and reports. The lab exists to answer one question before anything goes live: **does it beat the honest baseline on data it has never seen, after costs?**

## Protocol
1. **Pre-registration.** Before running a study, the hypothesis, features, label, cost model and pass criteria are written in the script header and in a spec document. They are not changed after the results are seen.
2. **Chronological splits.**
   - DEV (fitting): 2019-07 … 2023;
   - VAL: 2024;
   - TEST: 2025 … recent, opened once.
3. **Costs are realistic and pessimistic:**
   - commission;
   - one tick of slippage on market entries, stops and time exits;
   - a limit order counts as filled only if price trades **through** it by a tick;
   - if stop and target are hit in the same bar, the stop counts.
4. **Statistics.**
   - Day-block bootstrap, because trades within a day are correlated.
   - Paired comparisons (variant − baseline on the same days).
   - Removal tests: does removing trades by a rule beat removing the same number at random? This is the permutation control.
5. **Baselines.** Time-of-day frequency, "yesterday", HAR, implied-volatility scaling, a plain oscillator. A model has to beat the strongest baseline, not the weakest.
6. **Look-ahead hunting.** Every resample, rolling window and join is checked by recomputing the feature on data truncated at *t*. See [ENGINEERING_LOG.md](ENGINEERING_LOG.md#2-the-look-ahead-that-was-worth-1114-ticks).
7. **Failure is a result.** A FAIL is written up with the same care as a PASS. Live filters start in shadow mode even after a PASS.

## Research programmes (2026)

| Programme | Outcome |
|---|---|
| **Volatility / range:**<br/>• next hour (from minute bars);<br/>• day (from the overnight session, implied volatility and events). | Next-hour forecast beats the implied-volatility baseline by 31–45 % (QLIKE ratio 0.55 / 0.57 / 0.69 for ES / NQ / RTY on held-out data). Runs live in the cloud every minute. |
| **Timing of large moves** (no direction), around the clock | ROC AUC 0.71–0.84 by session on held-out years. Built into the engine as an index, used as a filter in shadow mode. |
| **Remaining range of the day** (exhaustion) | Calibrated estimate of the remaining expansion. Exhaustion is not a reversal signal. |
| **Order-book walls:** reaction, lifecycle, refills, iceberg viability | Drove the design of the wall registry and the entry gates of the production logic. |
| **Options open interest:** strike levels, pinning, gamma regime, overnight change | Tested on daily OI history; feeds an option-levels chart overlay. |
| **Execution:** fill rates of limits at walls, time-to-fill, stop placement, staged trailing, break-even | Calibrated on live journals (sub-second price paths of real trades). |
| **Live-vs-research forensics:** reconstructing live trades from journals, matching them to broker fills, auditing the side, R and costs | Several engine fixes; the same audit runs after every major release. |

## Working with external reviews
Studies and specs are regularly reviewed by external auditors (human and AI). Each point is checked against data and marked one of three ways:
- **confirmed** — taken into work;
- **refuted** — with the evidence;
- **plausible but untested** — turned into a test with a pass criterion.

Nothing is accepted or rejected wholesale.

## Related public code
- [`src/qs_range`](../src/qs_range) — the forecasting and evaluation toolkit in the same style as the production research code.
- [`docs/METHOD.md`](METHOD.md) — the forecast protocol summary.
