# 0002 — Capture each alert's full JSON; freeze the shaped table as legacy

**Status:** Accepted · **Date:** 2026-10-24

## Context
`bronze.mbta_alerts` was built by having the ingest shape each alert into chosen columns at alert × route grain. Everything else was dropped before it reached bronze:
- the stops each alert affects (`informed_entity`)
- every active period after the first (recurring closures)
- attributes like `lifecycle`, `service_effect`, and `closed_timestamp`

The API never returns an alert once it ends, so for every alert that ended before this change, those fields are gone. That contradicts [0001](0001-append-only-bronze.md).

## Decision
1. **Capture:** the alerts job also writes a second table, one row per alert per run holding the full JSON exactly as returned, alongside the unchanged shaped table. Capture began 2026-10-24 14:11 UTC (`alerts_raw_capture_start` in `dbt_project.yml`). It was first named `bronze.mbta_alerts_raw`; it's now `bronze.mbta_alerts` (see History).
2. **Reconcile:** raw split into alert × route with the ingest's own rules matched the shaped table for every run both were written: 32 runs, 704 rows, identical. The plan had been to wait weeks, but raw stores everything the API returns, so a bug in reading it would be fixed in SQL and rebuilt, with no data at risk. One clean day was enough to prove the logic.
3. **Cut over (same day):**
   - The ingest writes only raw; splitting into routes moved into `silver.mbta_alerts__by_route`.
   - That model reads the shaped table for snapshots before the capture start, and raw from then on. Once past the start, incremental runs never read the shaped table again.
   - The shaped table is no longer written. It's kept, frozen, as history of June–October 2026 that exists nowhere else, and **never deleted**.
   - It's renamed `bronze.mbta_alerts_legacy` ([0013](0013-bronze-tables-in-terraform.md) has the rename procedure). The date range goes in its description, not its name: BigQuery reads a trailing `_YYYYMMDD` in a table name as a date shard.

## Consequences
- Station-level history starts 2026-10-24 and can't be backfilled. `gold.rail_incidents.stations_affected` is NULL (unknown) for earlier incidents.
- Cost when decided (rail alerts only): ~2.6 GB/year, inside BigQuery's free storage for ~3–4 years, then pennies. [0011](0011-capture-every-mode.md) later widened capture to every mode and has the current rate.
- After the cutover, any new question about alerts can be answered from bronze without changing the ingest.

## History
- **2026-10-26:** with the raw table the only one written, it was renamed `bronze.mbta_alerts`, to match every other bronze table's `<source>_<entity>` name. `_raw` had been meant as a permanent marker for "records stored whole," but with one live alerts table it was just a break from the convention. It was renamed live, by the procedure in [0013](0013-bronze-tables-in-terraform.md), and no ingest run was missed. Silver's two incremental tables were renamed to match ([0010](0010-silver-naming-and-materialization.md)).
