# Roadmap

Planned work, roughly in order, with why. Move an item to a [decision record](decisions/) once it's decided, and delete it once it's done.

## Next

### Restructure silver with clear names
Silver mixes three kinds of models with nothing in their names to tell them apart:
- typed copies of one source (`mbta_routes`, `mbta_stops`, `mbta_ridership`, `noaa_weather`)
- incremental "latest version" tables (`mbta_alert_latest`, `mbta_alert_raw_latest`)
- multi-step business logic (`mbta_alerts` with 7 steps, and `mbta_alert_stops`)

The plan:
- Name models by role.
- Split `mbta_alerts` into "resolve start/end" and "group into incidents," so each step can be queried and tested.
- Keep gold names, since the dashboard reads them.
- Prove it's a pure refactor: gold must come out identical before and after.

**Open:** the naming scheme (see the conversation of 2026-10-24). Record the choice as a decision.

### Raw alert cutover ([0002](decisions/0002-raw-alert-capture.md))
Once `bronze.mbta_alerts_raw` has a few weeks of history (mid-November 2026 or later):
1. Reconcile: raw unpacked to alert × route matches `bronze.mbta_alerts` for the same runs.
2. Silver reads raw going forward and the old table for history, and the ingest stops writing the shaped table.
3. Rename the old table `bronze.mbta_alerts_legacy` (`ALTER TABLE … RENAME` plus Terraform import/removed blocks). Never delete it.

## Later

- **MBTA estimate accuracy model** (~January 2027). Are the MBTA's posted end times any good, and can a model beat them? This needs months of 15-minute snapshots (they began 2026-10-21). Early sign, from only 5 alerts: estimates sit ~2 hours out while delays clear in ~30 minutes.
- **Riders affected per disruption.** The ridership source is per station, but the ingest sums it per line. Station-level entries × stations affected would weight disruptions by the riders they hit.
- **Map line geometry.** Draw the lines themselves (MBTA shapes API) behind the station dots.

## Dated upkeep

| When | What |
|---|---|
| Before **2027-07-15** | Upgrade dbt (1.12 support ends); consider v2 ([0009](decisions/0009-runtime-versions.md)) |
| Before **2027-08-03** | tylerclifton.com renews; confirm auto-renew ([setup](setup.md#things-that-live-outside-the-repo)) |
| ~2029-10 | Python 3.13 support ends |
