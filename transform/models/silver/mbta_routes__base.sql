{#
  silver.mbta_routes__base — one row per route

  Latest snapshot of each rail route, plus the line it belongs to. Alerts are
  reported per route (Green-B, Green-C, ...) but ridership per line (Green Line),
  so line_name is the bridge between them.

  Steps:
    1. latest_versions — latest snapshot per route
    2. final select    — rename to project conventions, derive line_name,
                         label route_type
#}

WITH

    -- 1. Latest snapshot per route
    latest_versions AS (
        SELECT *
        FROM {{ source('bronze', 'mbta_routes') }}
        {{ keep_latest_version(['route_id']) }}
    )

-- 2. Project conventions: route_* attributes
SELECT
    route_id,
    long_name                                                   AS route_name,
    -- "Green Line B" → "Green Line"; falls back to the full name if the
    -- pattern ever stops matching (the accepted_values test will flag it)
    COALESCE(REGEXP_EXTRACT(long_name, r'^\w+ Line'), long_name) AS line_name,
    description                                                 AS route_description,
    -- GTFS route types used by MBTA rail
    CASE route_type
        WHEN 0 THEN 'Light Rail'
        WHEN 1 THEN 'Heavy Rail'
        ELSE CAST(route_type AS STRING)
    END                                                         AS route_type,
    color                                                       AS route_color,
    direction_destinations                                      AS route_destinations,
    ingested_at,
    ingested_by
FROM latest_versions
