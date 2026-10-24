# 0002 — Capture each alert's full JSON; later freeze the shaped table as legacy

**Status:** Accepted, cutover pending · **Date:** 2026-10-24

## Context
`bronze.mbta_alerts` was built by having the ingest shape each alert into chosen columns at alert × route grain. Everything else was dropped before it reached bronze:
- the stops each alert affects (`informed_entity`)
- every active period after the first (recurring closures)
- attributes like `lifecycle`, `service_effect`, and `closed_timestamp`

The API never returns an alert once it ends, so for every alert that ended before this change, those fields are gone. That contradicts [0001](0001-append-only-bronze.md).

## Decision
1. **Now:** the alerts job also writes `bronze.mbta_alerts_raw`, one row per alert per run holding the full JSON exactly as returned. The shaped table keeps being written, unchanged.
2. **Later, the cutover** (see [roadmap](../roadmap.md)):
   - After a few weeks, reconcile: raw unpacked to alert × route must match the shaped table for the same runs.
   - Silver then reads raw going forward and the old table for history, and the ingest stops writing the shaped table.
   - The old table is renamed `bronze.mbta_alerts_legacy` with BigQuery `ALTER TABLE … RENAME` plus Terraform import/removed blocks. A plain rename in Terraform would mean delete-and-recreate, which deletion protection blocks.
   - The legacy table is **never deleted**: it holds June–October 2026 alert history that exists nowhere else.
- `_raw` is a permanent name, marking a table that stores the source's records whole. Only the frozen table gets renamed.

## Consequences
- Station-level history starts 2026-10-24 and can't be backfilled. `gold.rail_incidents.stations_affected` is NULL (unknown) for earlier incidents.
- Cost: ~2.6 GB/year, inside BigQuery's free storage for ~3–4 years, then pennies.
- After the cutover, any new question about alerts can be answered from bronze without changing the ingest.
