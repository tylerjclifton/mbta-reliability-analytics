# 0015 — Ridership before the live layer comes from the MBTA's yearly archive, into the same bronze table

**Status:** Accepted · **Date:** 2026-11-03

## Context
The gated-entries feature service the ridership job pulls holds only the last two years (2024-10-01 to 2026-09-30 on 2026-11-03). Older days drop off it; bronze has kept every day since its first pull, which began at 2024-10-01.

The MBTA publishes the same data for earlier years as "MBTA Gated Station Entries – Historical": a 75 MB zip of one CSV per calendar year from 2014, with the layer's columns at its station × 30-minute grain. Checked 2026-11-03:
- **Against bronze**, where both have a day (2024-10-01 to 2026-09-30, 2,920 day × line rows): 2,775 matched to within one entry. The other 145 are all October and December 2024, from the archive's 2024 file, which undercounts most stations in those months (Blue Line −11% in October, Red Line −7% in December). The file looks to have been built before the MBTA's corrections reached the layer. The 2025 and 2026 files matched exactly.
- **Before 2024-10**, the archive has every day × line from 2019-01-01 to 2024-09-30.

A separate bronze table and job was rejected: it's the same data at the same grain with the same columns, and a second table would add a job, a schedule, a freshness check, and a silver union for one load.

## Decision
- The ridership job has an archive mode: `FROM_ARCHIVE=true`, set at execution time ([runbook](../runbook.md#backfill-ridership)). It sums each year's file to day × line, as the layer's query does, and appends days before 2024-10-01 (`ARCHIVE_BEFORE` in `ingest/mbta-gated-entries/main.py`) to `bronze.mbta_gated_entries`.
- From 2024-10-01 on, days come only from the layer. That date never moves: it's the first day bronze holds from the layer, and bronze keeps those days after the layer drops them. So the two never overlap, and `silver.mbta_gated_entries__base` is unchanged.
- It loads every year the archive has (2014 on). Weather was backfilled to 2014 to match.
- It runs once, not on a schedule. Re-run it if the MBTA revises past years; silver keeps the latest copy.

## Consequences
- Ridership starts 2014-01-01. Before 2024-10 the numbers are the archive's alone, with nothing to check them against; the MBTA notes the data "is not guaranteed to be complete for any stop or date."
- Bronze rows before 2024-10-01 are the archive's. They carry the same `ingested_by`; the date tells them apart.
- Alert history starts later than ridership, so early days have no incidents. That doesn't make them calm days on the dashboard: calm-day comparisons start when continuous alert tracking began (`coverage_start` in `serve/app.py`).

## History
- **2026-11-14:** `bronze.mbta_ridership` was renamed `bronze.mbta_gated_entries`, with its job (`ingest-mbta-gated-entries`) and silver model (`mbta_gated_entries__base`), named for what it counts now that the project measures ridership three ways ([0018](0018-ridership-for-every-mode.md)).
