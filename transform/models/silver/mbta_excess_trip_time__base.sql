{#
  silver.mbta_excess_trip_time__base — one row per half hour × line × direction

  Riders' trip times (wait plus travel) on the Red, Orange, and Blue Lines in
  each half hour of each service date against a baseline, the MBTA's
  estimates, as of each day's latest pull, in project conventions (decision
  0019). Minutes and the riders within each threshold are totals over the
  group's estimated riders: divide by riders_estimated for a rider's average.

  Each weekly run re-pulls the last 120 days, so bronze holds a service day
  once per run that covered it, and the latest run's rows stand, a whole day
  at a time, as for ferry trips.

  Steps:
    1. latest       — each service day's rows from the latest load that
                      covered it
    2. final select — renamed and typed
#}

WITH

    -- 1. Each service day's rows from the latest load that covered it.
    latest AS (
        SELECT *
        FROM {{ source('bronze', 'mbta_excess_trip_time') }}
        QUALIFY ingested_at = MAX(ingested_at) OVER (PARTITION BY service_date)
    )

-- 2. Project conventions. route_id is the line's GTFS route (Red, Orange,
--    Blue), as in silver.mbta_routes__base.
SELECT
    service_date,
    day                                 AS day_type,
    PARSE_TIME('%H:%M:%S', halfhour)    AS half_hour_start,
    peak                                AS service_period,
    route_id,
    dir_id                              AS direction,
    est_pax                             AS riders_estimated,
    weighted_trip_time                  AS trip_minutes,
    weighted_wait_time                  AS wait_minutes,
    weighted_travel_time                AS travel_minutes,
    weighted_bl_trip_time               AS baseline_trip_minutes,
    weighted_bl_wait_time               AS baseline_wait_minutes,
    weighted_bl_travel_time             AS baseline_travel_minutes,
    five_min_thresh                     AS riders_within_5_minutes,
    twenty_min_thresh                   AS riders_within_20_minutes,
    twenty_pct_thresh                   AS riders_within_20_percent,
    thirty_pct_thresh                   AS riders_within_30_percent,
    ingested_at,
    ingested_by
FROM latest
