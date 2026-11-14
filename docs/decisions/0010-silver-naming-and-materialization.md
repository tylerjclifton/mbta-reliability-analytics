# 0010 — Silver models are `<bronze table>__<step>`; views unless too costly to recompute

**Status:** Accepted · **Date:** 2026-10-24

## Context
Silver mixed three kinds of model with nothing in their names to tell them apart. Some were cleaned copies of one source (`mbta_routes`), some were incremental "latest version" tables (`mbta_alert_latest`), and some were multi-step business logic (`mbta_alerts`, 7 steps in one model). It even broke the existing rule that silver tables share their bronze table's name, since `silver.mbta_alerts` was the logic model.

dbt's conventional prefixes (`stg_` for "staging," `int_` for "intermediate") were considered and rejected. Neither name says what it stands for, and "staging" usually means an environment.

## Decision
**Every silver model is named `<bronze table>__<step>`:**
- **`__base`** is the cleaned copy (`mbta_alerts__base`, `mbta_stops__base`, …): the latest version of each record, renamed and typed, with no business rules.
- **Any other step** is named for what it produces, built from `__base` models or earlier steps. It's either a reshaping (`__by_route`, `__by_station`: the same alerts split by route or by station) or one business rule (`__resolved`, `__grouped`). Large rules are split so each step can be queried and tested on its own.

**Why this shape:**
- The prefix is the source a model is *about*, and the double underscore separates it from the step. Each source's models sort together, the lineage reads off the name, and no silver name is ambiguous.
- The step names the output, not the ingredients (not `_typed`, and not a list of joins), so names stay true when the logic changes.
- A step that applies rules is never called `__base`, even if it's the first one (`__resolved` drops notices and decides end times).
- A step's name shouldn't suggest a different grain. Alerts tagged with their incident are `__grouped`, not `__incidents`, since they're still one row per alert (one row per incident is `gold.rail_incidents`).
- The layer isn't in the name; the dataset (`silver.`) already says it. Gold names didn't change.

**Materialization:** everything in silver is a **view**, recomputed every run, unless recomputing it costs too much. Two kinds of exception are allowed: an **incremental table**, for a model that sits on all of bronze's history and can process only what's new (the alert snapshots grow at the rate in [0011](0011-capture-every-mode.md)); and a **table rebuilt every run**, for a model so many tests and models read that a view, rerun for each reader, costs more than building it once. Which models are exceptions is set in `transform/dbt_project.yml` and the models' own configs, and listed in the README's "Medallion layers".

## Consequences
- The refactor was proven pure: old and new code built against the same bronze produced identical gold (all 3,691 rows across four tables, compared both ways). Every later rename was proven the same way.
- In production, renamed models leave their old objects behind (dbt doesn't drop them), so they're dropped by hand after each deploy (`bq rm`). These are dbt's objects, not Terraform's, so this isn't drift ([0005](0005-terraform-only-changes.md)).
- The alerts cutover ([0002](0002-raw-alert-capture.md)) only touched `mbta_alerts__by_route`, which reads `bronze.mbta_alerts` plus legacy history; the steps after it didn't change.

## History
- **2026-10-24:** logic steps were first named on their own (`alerts_resolved`), and cleaned copies kept their bronze name exactly (`silver.mbta_alerts`). The steps scattered alphabetically and hid their source, and a bare name didn't say it was the cleaned copy, so both were standardized to the pattern above the same day.
- **2026-10-26:** the live alerts table was renamed `bronze.mbta_alerts` ([0002](0002-raw-alert-capture.md)). Its cleaned copy (latest JSON per alert) became `mbta_alerts__base` (from `mbta_alerts_raw__base`), and the per-route split became `mbta_alerts__by_route` (from `mbta_alerts__base`). Both are incremental tables, renamed in place so nothing was rebuilt. `__stations` became `__by_station` to match.
- **2026-11-03:** `lamp_alerts__base` became the third incremental table ([0016](0016-alerts-before-capture-from-lamp.md)): it reads bronze only after a new LAMP load.
- **2026-11-09:** `mbta_alerts__resolved`, `mbta_alerts__grouped`, and `mbta_alerts__by_station` became tables rebuilt every run, the second kind of exception. Each hourly run tested them 19 times, and a test on a view reruns its whole query: 760 of the run's 1,420 MiB. As tables, an hourly run billed 930 MiB (both measured 2026-11-09).
- **2026-11-12:** `mbta_alerts__base` now parses the JSON into the same typed columns as `lamp_alerts__base`, so each source is typed once, in its cleaned copy, as this record's `__base` rule says. `mbta_alerts__by_route` became a view that splits it by route, as `lamp_alerts__by_route` splits LAMP's, leaving two incremental tables. `mbta_alerts__by_period` joined the reshaping steps: every active period, beside the alert × route grain.
- **2026-11-14:** `mbta_ferry_trips__base` became the third incremental table ([0018](0018-ridership-for-every-mode.md)): each weekly ferry load re-pulls a year of legs, so it reads only new loads and replaces the service days they cover.
