# Forecast protocol (summary)

1. **Target.** ln(High/Low) of the session — a scale-free daily range (or a realised-variance proxy).
2. **Features.** Point-in-time only. Each feature of session D is built from data that existed before the forecast time.
3. **Split.** Chronological DEV → VAL → TEST.
   - Parameters are fitted on DEV and scored on VAL.
   - Then refitted on DEV+VAL and scored once on TEST.
4. **Baselines first:**
   - yesterday;
   - 22-day mean;
   - HAR in logs;
   - implied-volatility scaling.
5. **Candidates:**
   - HAR-X (OLS);
   - quantile HAR-X.

   Each extra feature must earn its place on VAL (≥ 1% loss improvement) and keep its coefficient sign across walk-forward refits.
6. **Acceptance — fixed before TEST:**
   - volatility: ≥ 3% QLIKE gain over HAR and DM p < 0.10;
   - range quantiles: ≥ 5% pinball gain and 80% interval coverage within ±4 pp;
   - probabilities: Brier skill > 0 and ECE ≤ 0.05.
7. **Failure is a result.** If a model fails, the best baseline ships. New models run in shadow mode before they influence anything.
