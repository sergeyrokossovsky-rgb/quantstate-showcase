# Engineering log — incidents and research traps

Short write-ups of real problems: how each was found and the rule it added. Specific trading parameters are omitted.

## 1. The 12-hour shift
**Symptom.** Order-book events from the recorder lined up with price moves "too well" on some days and not at all on others.

**Cause.** On some rows, the conversion between exchange time and UTC was off by exactly 12 hours (AM / PM).

**Fix.**
- Each row is corrected by rounding its offset to the nearest 12 hours.
- Then every recorded bar is cross-checked against vendor bars: 99.6–100 % exact close match.

**Rule.** Before any analysis, check what each timestamp column means against an independent source.

## 2. The look-ahead that was worth 11–14 ticks
**Symptom.** An oscillator-based filter improved a live logic by 11–14 ticks per trade in research.

**Cause.** The higher-timeframe bars were labelled and closed on the right. At the minute of entry, the "last closed bar" already contained that minute.

**Fix.**
- Left-closed, left-labelled resampling.
- The value is used only after the bar has closed.
- The feature is recomputed on data truncated at *t* — the effect disappeared.

**Rule.** Every resample and rolling feature is checked by truncation.

## 3. Limit orders that expired on 1-minute charts
**Symptom.** A client's robot logged entries that never reached the broker book for more than a minute.

**Cause.** Managed entry orders in NinjaTrader expire at the close of the bar of the series they were placed on. The owner runs 5-minute charts; the client ran a 1-minute chart.

**Fix.**
- All entry orders are now live until cancelled. The engine cancels them itself (time-to-live, distance abandon, limit timeout, time exit).
- Any cancel the engine did not request is detected immediately and resets state; before, the engine waited about 3 minutes for a timeout.
- The chart time frame is logged at start.

**Rule.** A platform default that depends on the user's chart is a production risk. Make it explicit.

## 4. A migration that failed without a sound
**Symptom.** Two new market-state cards in the admin panel stopped updating right after a deploy.

**Cause.** The first deploy created the table without a column that the second version writes. The insert failed on every minute, and the exception was swallowed.

**Fix.**
- An explicit migration plus a back-fill.
- A printed error with the bar time.
- A "data is stale" badge driven by the age of the last row.
- A test that starts from the old schema.

**Rule.** Every background job logs failures loudly, and every UI value shows its age.

## 5. A data-lag guard that cried wolf
**Symptom.** Dozens of false three-second lag alarms per night.

**Cause.** A few non-trade events carried a local-clock stamp about 18 s ahead of exchange time. They pulled the minimum-based baseline negative.

**Fix.**
- Measure trades only.
- Clamp the baseline at zero.
- Require the lag on consecutive trades and hold it for a few seconds.
- Add hysteresis on recovery.

**Rule.** Robust statistics on the right population, not on everything that has a timestamp.

## 6. A time exit lost at the session boundary
**Risk found in review.** An overnight position should close at the US open. At that moment the configuration switches to the day-session profile, which has a different exit time.

**Fix.**
- The deadline is computed in exchange time (DST-safe) and stamped on the position at entry.
- New entries are refused in the quiet period right after the exit time.

**Rule.** A property of a trade belongs to the trade, not to the configuration that happens to be active.

## 7. Selection artefacts that look like edge
**Trap.** Removing any subset of trades from a losing strategy improves its average. A filter that "removes the worst trades" can look like a PASS even if it is random.

**Fix.** Every removal filter is compared with removing the same number of trades at random (permutation control), on paired days.

**Rule.** "Better than before" is not evidence; "better than a random rule of the same size" is.

## 8. A biased intraday metric
**Trap.** The within-day correlation between a feature and the outcome was mechanically biased: both depend on the time already elapsed in the day.

**Fix.** Cross-day correlation computed separately for each time slot.

**Rule.** Make sure the metric is not measuring the clock.
