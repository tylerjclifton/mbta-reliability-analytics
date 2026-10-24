# 0002 — Capture each alert's full JSON; later freeze the shaped table as legacy

**Status:** Accepted, cut over 2026-10-24 · **Date:** 2026-10-24

## Context
`bronze.mbta_alerts` was built by having the ingest shape each alert into chosen columns at alert × route grain. Everything else was dropped before it reached bronze:
- the stops each alert affects (`informed_entity`)
- every active period after the first (recurring closures)
- attributes like `lifecycle`, `service_effect`, and `closed_timestamp`

The API never returns an alert once it ends, so for every alert that ended before this change, those fields are gone. That contradicts [0001](0001-append-only-bronze.md).

## Decision
1. **Capture:** the alerts job wrote `bronze.mbta_alerts_raw` too, one row per alert per run holding the full JSON exactly as returned, alongside the unchanged shaped table. Capture began 2026-10-24 14:11 UTC (`alerts_raw_capture_start` in `dbt_project.yml`).
2. **Reconcile:** raw split into alert × route with the ingest's own rules matched the shaped table for every run both were written: 32 runs, 704 rows, identical. The plan had been to wait weeks, but raw stores everything the API returns, so a bug in reading it would be fixed in SQL and rebuilt, with no data at risk. One clean day was enough to prove the logic.
3. **Cut over (same day):**
   - The ingest writes only raw; splitting into routes moved into `silver.mbta_alerts__base`.
   - That model reads the shaped table for snapshots before the capture start, and raw from it on. Once past the start, incremental runs never read the shaped table again.
   - The shaped table is no longer written. It's kept, frozen, as history of June–October 2026 that exists nowhere else, and **never deleted**.
   - It's then renamed `bronze.mbta_alerts_legacy`, with BigQuery `ALTER TABLE … RENAME` plus Terraform import/removed blocks. A plain rename in Terraform means delete-and-recreate, which deletion protection blocks. The date range goes in its description, not its name: BigQuery reads a trailing `_YYYYMMDD` in a table name as a date shard.
- `_raw` is a permanent name, marking a table that stores the source's records whole.

## Consequences
- Station-level history starts 2026-10-24 and can't be backfilled. `gold.rail_incidents.stations_affected` is NULL (unknown) for earlier incidents.
- Cost: ~2.6 GB/year, inside BigQuery's free storage for ~3–4 years, then pennies.
- After the cutover, any new question about alerts can be answered from bronze without changing the ingest.
