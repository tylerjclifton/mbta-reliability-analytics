# 0011 — Capture the whole alerts feed (every mode); silver keeps rail

**Status:** Accepted · **Date:** 2026-10-28

## Context
The alerts job requested only the 7 rail routes (`filter[route]`). Two things were being lost for good, since the API never returns an alert once it ends ([0001](0001-append-only-bronze.md)):
- **Every other mode.** The live feed held 158 alerts, and only 16 came back from the rail filter. Bus, commuter rail, and ferry alerts were never stored.
- **Rail accessibility alerts.** A route filter also applies the API's default activity filter (board, exit, ride), which drops escalator and elevator closures. The full feed held 25 rail alerts the filtered request didn't return, all escalator or elevator closures. Silver excludes those effects, so the dashboard never undercounted, but bronze wasn't complete as the ingest claimed.

Modeling other modes isn't worth it: the core analysis needs gated ridership, which only the subway has. Keeping their history is cheap, though, and can't be done later.

## Decision
- The alerts job requests the **whole feed**, starting 2026-10-28: no route filter, and `filter[activity]=ALL`. Bronze keeps every mode and every effect.
  - Why `ALL`: the API documents that a request without an activity filter defaults to board/exit/ride. In practice an otherwise unfiltered request already returned everything (150 alerts both ways on 2026-10-28), but `ALL` is the documented way to guarantee it, so the request doesn't rely on that behavior. Added the same day.
- **Silver keeps rail**, as it already did: `mbta_alerts__by_route` splits alerts only into the rail routes, and `mbta_alerts__by_station` keeps only routes in `mbta_routes__base`. No model changed. Before the switch, the full feed and the rail-filtered feed (fetched together) were run through silver's split logic: every rail row matched, and every stop the full feed named mapped to a known station.
- No bus, commuter rail, or ferry models. That data waits in bronze for a future project.
- **Routes and stops stay rail-only.** Unlike alerts, they aren't lost when they change: the MBTA publishes every past version of its schedule data (routes, stops, schedules) as archived GTFS feeds, back to 2009 (`https://cdn.mbta.com/archive/archived_feeds.txt`, 1,026 feeds on 2026-10-28). A future project that needs other modes' routes or stops, current or historical, can fetch them then.

## Consequences
- Bronze grows ~15 GB/year instead of ~2.6, measured from today's feed (415 KB per snapshot vs 74 KB). Storage is about $15–35 over five years, mostly at long-term rates (the table is partitioned by day).
- A full rebuild of the alert tables reads every snapshot, so it hits the 50 GiB per-query limit ([0004](0004-per-query-cost-limits.md)) around mid-2030, not ~2045. Hourly incremental runs are unaffected. See [roadmap](../roadmap.md).
- Every run now writes rows, so `silver.mbta_alerts__resolved` sees every ingest run. Before, a run with no rail alerts wrote nothing and left a gap in the run list that ended alerts were measured against.
- The rail route list now lives in three places that must match: `rail_routes` in `silver/mbta_alerts__by_route.sql`, and `TARGET_ROUTES` in the routes and stops ingests.
