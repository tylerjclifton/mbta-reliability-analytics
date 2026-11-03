# 0016 — Alerts from before full-JSON capture come from the MBTA's LAMP archive

**Status:** Accepted · **Date:** 2026-11-03

## Context
The project's own alert history is short and uneven: `bronze.mbta_alerts_legacy` from 2026-06-07 (shaped columns, no stops, and the pipeline was down June 8 – July 1), then full JSON in `bronze.mbta_alerts` from 2026-10-24 ([0002](0002-raw-alert-capture.md)).

The MBTA's LAMP archive keeps the same feed back to 2018 ([roadmap](../roadmap.md#the-mbtas-lamp-archive)). Subway alerts in it run continuously from **2019-09-05**: no gap of a week or more since then, about 100 service alerts a month. Before that it's sparse.

Compared with `silver.mbta_alerts__resolved` on 2026-11-03 (614 rail alert × route rows, June on):
- Every one is in LAMP; the effect matches on 613 and the start time on all.
- **End times.** LAMP's close time is the API's own `closed_timestamp`: on the 27 alerts a snapshot caught after closing, the two matched to the second. Silver estimates the end from when an alert left the feed instead, because alerts leave the API a few minutes after closing.
  - Full-JSON era: close is a median 4 minutes before silver's end, 90% within 11 minutes.
  - Old pipeline: a median 11 minutes before, spread −31 to +18 minutes, since most of its alerts were seen in a single snapshot.
  - Alerts open across the June gap end at the last run before it. One Green Line station closure ends June 7 in silver; LAMP closed it June 22.

## Decision
- **Bronze.** `bronze.lamp_alerts` holds LAMP's file as published: every mode, every year. The `ingest-lamp-alerts` job loads it on demand, with no schedule and no freshness check ([runbook](../runbook.md#load-the-lamp-alerts-archive)).
- **Rail alerts that ended before full-JSON capture** (`alerts_raw_capture_start`) come from LAMP, from 2019-09-05 on. Each ends at LAMP's close time, or its posted end if that's earlier, as the current rule already treats the posted end.
- **From the capture start on,** alerts come from the project's own snapshots, unchanged.
- **The legacy table stays** in bronze, frozen and never deleted, but no model reads it: LAMP covers the same months with stops and more precise ends.
- **LAMP rows are immutable versions.** Silver keeps distinct rows across loads, so a partial or repeated load can't drop or double an alert.
- Only data the API also provides is taken from LAMP ([roadmap](../roadmap.md#the-mbtas-lamp-archive)).

## Consequences
- Incident history starts 2019-09-05; the June gap is filled; stations are known for every alert.
- Durations before the capture start run about 4 minutes shorter on median than after it (close time vs. leaving the feed). A possible follow-up: use `closed_timestamp` in the project's own rule whenever a snapshot catches it.
- Old alerts can name stops that no longer exist (Lechmere moved, and the Green Line Extension opened, 2020–22). Those stations need the archived GTFS for their date to reach the map; line-level counts don't depend on them.
- LAMP rewrites its file in place and could change; bronze keeps each loaded copy ([0001](0001-append-only-bronze.md)).
- Each load is ~5M rows. Silver processes it once into small incremental tables, so the hourly transform never re-reads it.
