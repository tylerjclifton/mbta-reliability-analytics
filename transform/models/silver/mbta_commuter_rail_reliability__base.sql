{#
  silver.mbta_commuter_rail_reliability__base — one row per row of the file

  Commuter rail trains measured, on time, and canceled for a line or branch,
  service date, and peak or off-peak period, as of each day's latest pull, in
  project conventions (decision 0019). A line can have several rows for one
  day and period, its branches published as parts of it, sometimes under the
  same name; sum the counts per line before dividing, as the MBTA intends.

  Each weekly run re-pulls the last 120 days, so bronze holds a service day
  once per run that covered it. With no key to match rows on, the latest
  run's rows stand a whole day at a time, as for ferry trips.

  Steps:
    1. latest       — each service day's rows from the latest load that
                      covered it
    2. final select — renamed and typed
#}

WITH

    -- 1. Each service day's rows from the latest load that covered it.
    latest AS (
        SELECT *
        FROM {{ source('bronze', 'mbta_commuter_rail_reliability') }}
        QUALIFY ingested_at = MAX(ingested_at) OVER (PARTITION BY service_date)
    )

-- 2. Project conventions. The other published columns hold one value each
--    (Commuter Rail, NA, Headway / Schedule Adherence) and are left out.
SELECT
    service_date,
    gtfs_route_id                   AS route_id,
    gtfs_route_long_name            AS route_part_name,
    peak_offpeak_ind = 'PEAK'       AS is_peak,
    otp_denominator                 AS trains_measured,
    otp_numerator                   AS trains_on_time,
    canceled_numerator              AS trains_canceled,
    ingested_at,
    ingested_by
FROM latest
