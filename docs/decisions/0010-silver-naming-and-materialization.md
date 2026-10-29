# 0010 — Silver models are `<bronze table>__<step>`; views unless too costly to recompute

**Status:** Accepted · **Date:** 2026-10-24 (names refined 2026-10-24 and 2026-10-26)

## Context
Silver mixed three kinds of model with nothing in their names to tell them apart. Some were cleaned copies of one source (`mbta_routes`), some were incremental "latest version" tables (`mbta_alert_latest`), and some were multi-step business logic (`mbta_alerts`, 7 steps in one model). It even broke the existing rule that silver tables share their bronze table's name, since `silver.mbta_alerts` was the logic model.

dbt's conventional prefixes (`stg_` for "staging," `int_` for "intermediate") were considered and rejected. Neither name says what it stands for, and "staging" usually means an environment.

## Decision
**Every silver model is named `<bronze table>__<step>`:**
- **`__base`** is the cleaned copy (`mbta_alerts__base`, `mbta_stops__base`, …): the latest version of each record, renamed and typed, with no business rules.
- **Any other step** is named for what it produces (`mbta_alerts__by_route`, `mbta_alerts__by_station`, `mbta_alerts__resolved`, `mbta_alerts__grouped`), built from `__base` models or earlier steps: a reshaping (`__by_route`, `__by_station`: the same alerts split by route or by station) or one business rule. Large rules are split so each step can be queried and tested on its own.

The prefix is the source a model is *about*, and the double underscore separates it from the step. Each source's models sort together, the lineage reads off the name, and no silver name is ambiguous. The step names the output, not the ingredients (not `_typed`, and not a list of joins), so names stay true when the logic changes. A step that applies rules is never called `__base`, even if it's the first one (`__resolved` drops notices and decides end times). A step's name shouldn't suggest a different grain: alerts tagged with their incident are `__grouped`, not `__incidents`, since they're still one row per alert (one row per incident is `gold.rail_incidents`). The layer isn't in the name; the dataset (`silver.`) already says it. Gold names didn't change.

How it got here: on 2026-10-24, logic steps were first named on their own (`alerts_resolved`) and cleaned copies kept their bronze name exactly (`silver.mbta_alerts`). The steps scattered alphabetically and hid their source, and a bare name didn't say it was the cleaned copy, so both were standardized to the pattern above the same day. On 2026-10-26, the live alerts table was renamed `bronze.mbta_alerts` ([0002](0002-raw-alert-capture.md)). Its cleaned copy (latest JSON per alert) became `mbta_alerts__base`, and the per-route split became `mbta_alerts__by_route`; `__stations` became `__by_station` to match.

**Materialization:** everything in silver is a **view**, recomputed every run, except tables that would cost too much to recompute: today `mbta_alerts__base` and `mbta_alerts__by_route`, which sit on 15-minute snapshots growing ~15 GB/year. Those are incremental tables that process only new snapshots.

## Consequences
- The refactor was proven pure: old and new code built against the same bronze produced identical gold (all 3,691 rows across four tables, compared both ways).
- In production, renamed models leave their old objects behind (dbt doesn't drop them), so they're dropped by hand after each deploy (`bq rm`). Every rename was proven pure the same way.
- The alerts cutover ([0002](0002-raw-alert-capture.md)) only touched `mbta_alerts__by_route`, which reads `bronze.mbta_alerts` plus legacy history; the steps after it didn't change.
