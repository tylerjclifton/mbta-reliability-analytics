{#
  gold.rail_stations — one row per station × line

  Every rail station with its coordinates, once per line it serves (Park Street
  is on both the Red and Green Lines). The dashboard draws these as the map's
  backdrop and filters them with the line selector.

  Steps:
    1. station_routes — each station's own row, per route serving it
    2. final select   — collapsed to station × line
#}

WITH

    -- 1. Stations (not their platforms) with each route's line
    station_routes AS (
        SELECT
            s.station_id,
            s.station_name,
            s.stop_latitude,
            s.stop_longitude,
            s.is_wheelchair_accessible,
            r.line_name,
            s.ingested_at
        FROM {{ ref('mbta_stops') }} AS s
        INNER JOIN {{ ref('mbta_routes') }} AS r
            ON s.route_id = r.route_id
        WHERE s.stop_type = 'Station'
    )

-- 2. One row per station × line (Green Line branches share their trunk stations)
SELECT
    station_id,
    line_name,
    ANY_VALUE(station_name)             AS station_name,
    ANY_VALUE(stop_latitude)            AS station_latitude,
    ANY_VALUE(stop_longitude)           AS station_longitude,
    ANY_VALUE(is_wheelchair_accessible) AS is_wheelchair_accessible,
    MAX(ingested_at)                    AS ingested_at
FROM station_routes
GROUP BY
    station_id,
    line_name
