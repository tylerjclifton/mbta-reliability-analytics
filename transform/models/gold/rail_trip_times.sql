{#
  gold.rail_trip_times — one row per service date × line × service period

  How long riders' trips took on the Red, Orange, and Blue Lines against a
  baseline, the MBTA's estimates (decision 0019). Totals, so the dashboard can
  add any span before dividing: trip_minutes / riders_estimated is a rider's
  average trip, (trip_minutes - baseline_trip_minutes) / riders_estimated the
  extra minutes it took, slow zones and delays alike. The MBTA doesn't
  estimate the Green Line.

  Steps:
    1. final select — per day × line × period, with the line's name
#}

-- 1. Per day × line × period; a day has one day type.
SELECT
    t.service_date,
    r.line_name,
    t.service_period,
    ANY_VALUE(t.day_type)               AS day_type,
    SUM(t.riders_estimated)             AS riders_estimated,
    SUM(t.trip_minutes)                 AS trip_minutes,
    SUM(t.baseline_trip_minutes)        AS baseline_trip_minutes,
    SUM(t.wait_minutes)                 AS wait_minutes,
    SUM(t.baseline_wait_minutes)        AS baseline_wait_minutes,
    SUM(t.travel_minutes)               AS travel_minutes,
    SUM(t.baseline_travel_minutes)      AS baseline_travel_minutes,
    SUM(t.riders_within_5_minutes)      AS riders_within_5_minutes,
    SUM(t.riders_within_20_minutes)     AS riders_within_20_minutes,
    MAX(t.ingested_at)                  AS ingested_at
FROM {{ ref('mbta_excess_trip_time__base') }} AS t
LEFT JOIN {{ ref('mbta_routes__base') }} AS r
    ON t.route_id = r.route_id
GROUP BY
    t.service_date,
    r.line_name,
    t.service_period
