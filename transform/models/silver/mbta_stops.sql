{#
  silver.mbta_stops — one row per stop × route

  Latest snapshot of every rail station and the stops inside it (platforms,
  entrances, walkway nodes), each mapped to its station. Alerts name the stops
  they affect mostly by platform; station_id rolls those up to the station a
  rider would recognize, and gives it coordinates for the dashboard's map.

  route_id is the route whose stations were requested, so a station and its
  child stops repeat for each route serving it (Park Street: Red and every
  Green branch). For a child stop it says which route's station it's in, not
  which route stops at it.

  Steps:
    1. latest_versions — latest snapshot per stop × route
    2. final select    — rename to project conventions, resolve station_id,
                         label location_type
#}

WITH

    -- 1. Latest snapshot per stop × route
    latest_versions AS (
        SELECT *
        FROM {{ source('bronze', 'mbta_stops') }}
        {{ keep_latest_version(['stop_id', 'route_id']) }}
    )

-- 2. Project conventions: stop_* attributes; a station is its own station
SELECT
    stop_id,
    route_id,
    COALESCE(parent_station_id, stop_id) AS station_id,
    -- Platforms and other child stops carry their station's name
    stop_name                            AS station_name,
    -- GTFS location types
    CASE location_type
        WHEN 0 THEN 'Platform'
        WHEN 1 THEN 'Station'
        WHEN 2 THEN 'Entrance'
        WHEN 3 THEN 'Node'
        WHEN 4 THEN 'Boarding Area'
        ELSE CAST(location_type AS STRING)
    END                                  AS stop_type,
    platform_name                        AS stop_platform_name,
    latitude                             AS stop_latitude,
    longitude                            AS stop_longitude,
    municipality                         AS stop_municipality,
    -- GTFS wheelchair_boarding: 0 = no information
    CASE wheelchair_boarding
        WHEN 1 THEN TRUE
        WHEN 2 THEN FALSE
    END                                  AS is_wheelchair_accessible,
    ingested_at,
    ingested_by
FROM latest_versions
