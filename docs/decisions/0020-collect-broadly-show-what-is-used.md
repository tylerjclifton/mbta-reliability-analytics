# 0020 — Collect broadly, show what's used; retire a bronze table only when bronze holds it elsewhere

**Status:** Accepted · **Date:** 2026-11-16

## Context
A cleanup review found data the project collected but didn't show: every mode's alerts beyond the subway ([0011](0011-capture-every-mode.md)), commuter rail reliability, taken off the dashboard the day before ([0019](0019-reliability-riders-feel.md)), and the frozen `bronze.mbta_alerts_legacy`, which no model had read since LAMP covered its months ([0016](0016-alerts-before-capture-from-lamp.md)).

Two aims pull against each other. A lean project stores and shows only what it uses. But no public agency promises to keep its data: the MBTA's alerts API forgets an alert once it ends, LAMP is one file the MBTA rewrites in place, and its open data files can be replaced or withdrawn. That's why bronze never relies on a source keeping history ([0001](0001-append-only-bronze.md)). Storage costs pennies; lost history can't be bought back.

## Decision
- **Collect broadly.** Bronze takes data that's cheap to keep and could change or vanish, whether or not the dashboard shows it yet: every mode's alerts, commuter rail reliability, and the whole of each published file, columns the models don't read included.
- **Model and show only what's used.** Silver, gold, and the dashboard hold only what the site shows; a model the site stops using is removed, and can be rebuilt from bronze.
- **The dashboard shows riders on every mode, and punctuality wherever the MBTA publishes it for every trip:** the subway's trip times, commuter rail's reliability file, and the ferry's trip legs. Bus has none, only a very large arrival file the project doesn't take. This brings back the commuter rail and ferry punctuality removed on 2026-11-15.
- **A bronze table may be deleted only when bronze holds the same data elsewhere.** The first is `bronze.mbta_alerts_legacy`: its months (2026-06-07 to 2026-10-24) are in `bronze.lamp_alerts`, with stops and the MBTA's close times, and every rail alert of the period matched ([0016](0016-alerts-before-capture-from-lamp.md)). It's retired in two pushes ([runbook](../runbook.md#retire-a-bronze-table)).

## Consequences
- Everything in silver, gold, and on the dashboard is used. What bronze holds beyond that is deliberate, and this record says why.
- Bronze shrinks only by the one exception, and never loses data the project doesn't hold elsewhere.
- Deleting the legacy table saves next to nothing (10 MB); the gain is a bronze where every table is either live or a deliberate archive.
