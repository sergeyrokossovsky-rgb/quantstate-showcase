# QS Pulse — a forecast graded in public

QS Pulse publishes, every NYSE trading day, an 80% band for the S&P 500 session range (SPY High / Low) and grades it after the close. The page shows every forecast with the time it was fixed, and every miss stays in the ledger. Nothing is back-filled.

## Why a public forecast
A trading-software company is easy to doubt. A number fixed before the bell and graded by the market after the close cannot be edited later. The forecast is a by-product of the lab's volatility research — the same research that tells the trading engine when to stand aside.

## Inputs
**Only non-CME data** (deliberate — derived products of exchange data need a licence):
- recent daily SPY ranges — HAR lags: yesterday, week, month;
- the previous VIX close;
- the opening gap;
- the FOMC / NFP calendar.

**Not published:** the exact model specification and coefficients — they are proprietary.

## Validation (fixed protocol)
**Protocol:**
- fit on 2019-07 … 2024;
- one look at 2025-01 … 2026-10-12, which the model never saw — 439 sessions;
- the feature set and the variants were fixed before the test period was opened.

| | Result |
|---|---|
| Sessions inside the 80% band | **81.3 %** (357 / 439) |
| Volatility-forecast error vs the VIX-implied forecast (QLIKE) | **−28 %** |
| Range-quantile error vs the VIX-implied forecast (pinball) | **−10 %** |
| Every quantile's hit rate | within ±3 pp of its level |
| "Extreme day" probability (top 5 %) | Brier skill 0.32, calibration error 0.016 |

**Event days, 2025–26** (median range vs ordinary days):
- jobs report 1.30×;
- Fed decision 1.28×;
- CPI 1.07×.

**Fallbacks**, validated the same way and used automatically when an input is missing:
- no gap: 80.9 %, −27 %;
- no VIX: 80.0 %, −21 %.

## Production pipeline
1. **9:35 ET.** The band is fixed once (immutable row), only on full sessions — NYSE holidays and early closes are skipped by a rule-based calendar ([`src/qs_pulse/calendar.py`](../src/qs_pulse/calendar.py)).
2. **After the close.** The official daily bar arrives → inside / above / below ([`src/qs_pulse/record.py`](../src/qs_pulse/record.py)).
3. **Cards (1200×675 PNG)** are rendered in a headless browser, sent to the owner's Telegram for approval, then posted to X (API v2, OAuth 2.0 with PKCE and rotating refresh tokens) and to a Facebook Page (Graph API).
4. **The weekly card** shows the engine's live demo account in ticks per contract after costs, losing weeks included.

## Engineering rules applied
- **A forecast is written once.** Grading fills two fields and never touches the band.
- **The public API returns only the published fields** — never internal indices or model inputs. A test enforces it.
- **Every post can be held for approval**, and the weekly result always needs it.
- **Marketing e-mail** goes through a suppression list with one-click unsubscribe (RFC 8058 headers) and a company postal address.
