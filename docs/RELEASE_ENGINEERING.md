# Release engineering

One code base, two products per release:

| Build | For | Contents |
|---|---|---|
| **Developer** | the owner's trading PC | full diagnostics, research taps (recorder hooks, extended journals, telemetry of shadow logic), embedded research models |
| **Commercial** | clients | slim diagnostics, journals stay on the client PC, models are delivered by the server at start instead of being compiled in, obfuscated assemblies |

## Release steps
1. **Spec first.** Every release starts as a written spec. It lists what changes in trading behaviour (often: nothing — new parts start in shadow mode), every file touched and the checks to run after deployment.
2. **Source integrity.** The engine sources in the repository and in the NinjaTrader installation are compared byte by byte. Syntax is checked by a parser before the platform compiler runs.
3. **Server tests.** Parameter schema, OTA encoding, validator and robot-side source checks (for example, "no entry order may use bar-close expiry").
4. **Build.** One click per variant:
   - compile;
   - obfuscate (Commercial);
   - pack the installer;
   - write a SHA-256 manifest;
   - print the assembly hash.
5. **Register.** The assembly hash of each variant is registered on the server. An unregistered build cannot obtain a licence session.
6. **Publish.**
   - Installers are uploaded.
   - The release is published with notes.
   - The Commercial build becomes the current version; the Developer build is published on its own channel.
   - The CDN cache is purged.
7. **Verify live.** Expected start-up lines in the platform log (version, chart time frame, model source, data-lag baseline) and expected rows in the server tables within minutes.

## Over-the-air updates
- **Staging.** The installed bootstrapper stages the whole new installer and runs it silently after the platform exits.
- **No mixed versions.** A downgrade guard and a version stamp prevent mixed versions.
- **Configuration is not a release.** Configuration changes (session profiles, logic switches) are pushed without any release.

## Cadence
40 releases in the current 71.0.x line. Small non-trading fixes are batched and shipped together with a larger change, so that clients do not update for cosmetic reasons.
