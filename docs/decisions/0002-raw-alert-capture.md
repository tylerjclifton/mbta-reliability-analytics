# 0002 — Capture each alert's full JSON; freeze the shaped table as legacy

**Status:** Accepted, cut over 2026-10-24, tables renamed 2026-10-26 · **Date:** 2026-10-24

## Context
`bronze.mbta_alerts` was built by having the ingest shape each alert into chosen columns at alert × route grain. Everything else was dropped before it reached bronze:
- the stops each alert affects (`informed_entity`)
- every active period after the first (recurring closures)
- attributes like `lifecycle`, `service_effect`, and `closed_timestamp`

The API never returns an alert once it ends, so for every alert that ended before this change, those fields are gone. That contradicts [0001](0001-append-only-bronze.md).

## Decision
1. **Capture:** the alerts job wrote a second table too (`bronze.mbta_alerts_raw`, now named `bronze.mbta_alerts`), one row per alert per run holding the full JSON exactly as returned, alongside the unchanged shaped table. Capture began 2026-10-24 14:11 UTC (`alerts_raw_capture_start` in `dbt_project.yml`).
2. **Reconcile:** raw split into alert × route with the ingest's own rules matched the shaped table for every run both were written: 32 runs, 704 rows, identical. The plan had been to wait weeks, but raw stores everything the API returns, so a bug in reading it would be fixed in SQL and rebuilt, with no data at risk. One clean day was enough to prove the logic.
3. **Cut over (same day):**
   - The ingest writes only raw; splitting into routes moved into `silver.mbta_alerts__by_route`.
   - That model reads the shaped table for snapshots before the capture start, and raw from it on. Once past the start, incremental runs never read the shaped table again.
   - The shaped table is no longer written. It's kept, frozen, as history of June–October 2026 that exists nowhere else, and **never deleted**.
   - It's then renamed `bronze.mbta_alerts_legacy`, with BigQuery `ALTER TABLE … RENAME` plus a Terraform `import` block to adopt it under the new name (removed once applied). A plain rename in Terraform means delete-and-recreate, which deletion protection blocks. The date range goes in its description, not its name: BigQuery reads a trailing `_YYYYMMDD` in a table name as a date shard.
4. **Names (2026-10-26):** once the raw table was the only one written, it was renamed `bronze.mbta_alerts` to match every other bronze table's `<source>_<entity>` name. `_raw` had been meant as a permanent marker for "records stored whole," but with only one live alerts table it was just a difference from the convention. That rename touched a live table, so ingestion was protected:
   - It ran right after a 15-minute ingest run.
   - The alerts job was pointed at the new name within seconds, before any run could fire.
   - A manual ingest run confirmed rows landed in the renamed table before the code was pushed.
   - Silver's two incremental tables were renamed the same way (`mbta_alerts_raw__base` → `mbta_alerts__base`, `mbta_alerts__base` → `mbta_alerts__by_route`), so nothing was rebuilt.

## Consequences
- Station-level history starts 2026-10-24 and can't be backfilled. `gold.rail_incidents.stations_affected` is NULL (unknown) for earlier incidents.
- Cost: ~2.6 GB/year, inside BigQuery's free storage for ~3–4 years, then pennies.
- After the cutover, any new question about alerts can be answered from bronze without changing the ingest.
