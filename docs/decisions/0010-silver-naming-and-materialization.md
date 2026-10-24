# 0010 — Silver: cleaned copies and logic steps; views unless too costly to recompute

**Status:** Accepted · **Date:** 2026-10-24 (logic-step names revised the same day)

## Context
Silver mixed three kinds of model with nothing in their names to tell them apart. Some were cleaned copies of one source (`mbta_routes`), some were incremental "latest version" tables (`mbta_alert_latest`), and some were multi-step business logic (`mbta_alerts`, 7 steps in one model). It even broke the existing rule that silver tables share their bronze table's name, since `silver.mbta_alerts` was the logic model.

dbt's conventional prefixes (`stg_` for "staging," `int_` for "intermediate") were considered and rejected. Neither name says what it stands for, and "staging" usually means an environment.

## Decision
**Two kinds of silver model, told apart by name:**
- **Cleaned copies** are named exactly like their bronze table (`mbta_alerts`, `mbta_stops`, …). Each holds the latest version of each record, renamed and typed, with no business rules.
- **Logic steps** are named `<cleaned copy>__<what the step produces>`: `mbta_alerts__resolved`, `mbta_alerts__incidents`, `mbta_alerts__stations`. Each holds one business rule, built from that cleaned copy (plus others as needed) or earlier steps. Large rules are split so each step can be queried and tested on its own.

The prefix is the source the step is *about*, and the double underscore separates it from the step, so each source's models sort together and the lineage reads off the name. The suffix names the output, not the ingredients (not `_typed`, and not a list of joins), so names stay true when the logic changes. The layer isn't in the name; the dataset (`silver.`) already says it. Gold names didn't change.

The first version of this decision named logic steps on their own (`alerts_resolved`, `alert_incidents`, `alert_stations`). Those scattered alphabetically and hid which source they came from, so they were renamed the same day.

**Materialization:** everything in silver is a **view**, recomputed every run, except tables that would cost too much to recompute: today `mbta_alerts` and `mbta_alerts_raw`, which sit on 15-minute snapshots growing ~3.6 GB/year. Those are incremental tables that process only new snapshots.

## Consequences
- The refactor was proven pure: old and new code built against the same bronze produced identical gold (all 3,691 rows across four tables, compared both ways).
- In production, renamed models leave their old objects behind (dbt doesn't drop them), so they're dropped by hand after each deploy (`bq rm`). Both renames were proven pure the same way.
- The raw alert cutover ([0002](0002-raw-alert-capture.md)) now touches only the cleaned copies: `mbta_alerts` will read raw plus legacy history. The logic steps don't change.
