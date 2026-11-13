# Cloud platform

Python / FastAPI in Docker behind Cloudflare. Production size:
- ≈ 50 000 lines of Python;
- 298 HTTP endpoints;
- 89 database tables;
- 769 automated tests in 133 files.

It serves three audiences: the installed robots, the clients and the owner.

## Services

| Service | What it does |
|---|---|
| **Licensing** | Licence keys bound to hardware; robot tokens; assembly-hash verification (a build whose hash is not registered is refused); per-product entitlements (engine, order-book product, bundles). |
| **Over-the-air configuration** | 632 typed parameters per instrument with ranges, Russian / English hints and validation. Session profiles (day session / overnight / closed) are versioned, published and pushed into running robots without a restart. A canary roll-out goes to selected licences first. Per-licence overrides switch individual logics on or off. |
| **Software updates** | Signed releases, current-version pointer, Developer / Commercial channels; the client installs updates from inside the platform. |
| **Telemetry** | Heartbeats, every signal and trade, shadow journals, data-lag alerts, crash reports; trade reconciliation against client-reported fills. |
| **Live index service** | Receives minute bars from the trading PC every minute and computes the indices immediately: volatility for the next hour, its range quantiles, market state (readiness for a large move, share of the expected day range covered). It back-fills the realised outcome an hour later, so accuracy is measured live. |
| **Market intelligence** | Daily and intraday market-state scores; macro calendar; earnings reactions of the largest index members (EDGAR / XBRL); options open-interest pipeline; daily range forecast. 14 modules on a scheduler. |
| **Admin panel** | Session-profile editor with parameter sections that follow the engine's decision path; fleet overview; client 360° view; period reports of every index and shadow journal with Excel / CSV export. |
| **Client portal** | Products, downloads, licence status, installation guide, invoices, subscription management, partner dashboard. |
| **Billing** | Stripe subscriptions with phased introductory prices, webhook-driven state, tax-inclusive pricing, PDF invoices; promo codes for sales agents with a 12-month commission ledger. |
| **Telegram** | Owner and client bots: PNG market cards (Jinja2 → headless Chromium), trade alerts, monitors, commands. 14 modules. |
| **Website** | 63 pages, Russian / English, legal documents, pricing, activation. |

## Engineering rules
- **Secrets never in code or chat.** Keys live in the server environment and are generated on the server. Upload keys are scoped to one purpose (for example, "may only send bars").
- **Migrations are explicit and loud.** A schema change ships with a migration and a test that starts from the previous schema. See [ENGINEERING_LOG.md](ENGINEERING_LOG.md#4-a-migration-that-failed-without-a-sound).
- **Every external input degrades gracefully.** Missing or stale data is marked as such in the UI ("data is stale") and in the API, never silently replaced.
- **Validation is shared.** One parameter schema feeds the admin form, the OTA encoder, the validator and the robot-side sanitizer. Each new key is covered by a test across all four.
