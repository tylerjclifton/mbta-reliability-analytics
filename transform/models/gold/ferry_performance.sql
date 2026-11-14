{#
  gold.ferry_performance — one row per month × ferry route

  How many rode each ferry route and how punctual it was, month by month, from
  every trip leg (silver.mbta_ferry_trips__base).

  On time is the MBTA's own measure: departing no more than 5 minutes after
  schedule. Computed this way, it matches the MBTA's published monthly figures
  (MBTA Ferry Reliability) within about a point on every route in 2024–25;
  adding arrivals would not (Lynn's boats leave on time but land a few minutes
  past tight scheduled arrivals: 99% vs 75%). A leg is measured only if its
  departure is known and plausible, from an hour early to four hours late;
  outside that, its times are data errors (a few hundred legs dated a day or
  a month off), not late boats.

  Steps:
    1. legs         — each leg's month, route name, riders, and delay
    2. final select — per month × route: legs, riders, days of service, and
                      the share of measured legs on time
#}

WITH

    -- 1. Each leg, under its route's place name: route_name drops its ID and
    --    gains the spaces it lacks (F9 is published under F8's name, so the
    --    two Quincy/Winthrop routes join).
    legs AS (
        SELECT
            service_date,
            DATE_TRUNC(service_date, MONTH)                                       AS month_start,
            CASE REGEXP_EXTRACT(route_name, r'^[^-]+-(.+)$')
                WHEN 'EastBoston' THEN 'East Boston'
                WHEN 'QuincyWinthrop' THEN 'Quincy/Winthrop'
                ELSE REGEXP_EXTRACT(route_name, r'^[^-]+-(.+)$')
            END                                                                   AS route_name,
            riders_on,
            TIMESTAMP_DIFF(actual_departure_at, scheduled_departure_at, MINUTE)   AS departure_delay_minutes
        FROM {{ ref('mbta_ferry_trips__base') }}
    )

-- 2. Per month × route.
SELECT
    month_start,
    route_name,
    COUNT(*)                                       AS legs,
    SUM(riders_on)                                 AS riders,
    COUNT(DISTINCT service_date)                   AS service_days,
    COUNTIF(is_measured)                           AS measured_legs,
    COUNTIF(is_measured AND is_on_time)            AS on_time_legs,
    SAFE_DIVIDE(COUNTIF(is_measured AND is_on_time), COUNTIF(is_measured)) AS on_time_share
FROM (
    SELECT
        *,
        departure_delay_minutes BETWEEN -60 AND 240 AS is_measured,
        departure_delay_minutes <= 5                AS is_on_time
    FROM legs
) AS judged
GROUP BY
    month_start,
    route_name
