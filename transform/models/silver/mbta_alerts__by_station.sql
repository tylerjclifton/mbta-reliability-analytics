{#
  silver.mbta_alerts__by_station — one row per alert × route × station

  Which stations each alert affects, from the stop list (informed_entity) in
  its latest version: the full JSON for alerts seen since full-JSON capture,
  LAMP's entities for alerts before it (silver.lamp_alerts__base; decision
  0016). A bridge table: alerts stay one row per alert × route
  (silver.mbta_alerts__grouped), and this adds the stations alongside them
  rather than changing that grain.

  The MBTA lists stops mostly by platform (often one per direction); those
  roll up to their station here, with whether the alert affects one direction
  or both. Alerts that name no stops (most delays are line-wide) have no rows.
  Covers every effect, like silver.mbta_alerts__base; gold joins it to
  silver.mbta_alerts__grouped, which keeps only service-affecting alerts.

  LAMP's stops that no longer exist are left out: ten retired Green Line B
  branch platforms (stop IDs 70136–70145, named through 2021), about 1% of
  rows on 2026-11-04. They have no station or coordinates to map, and the map
  only covers the last 12 months. A stop the live JSON names but the stops
  reference doesn't know yet keeps its own ID instead (below).

  Steps:
    1. entities     — one row per stop entry in each alert's informed_entity,
                      from the JSON or, for alerts it lacks, from LAMP
    2. stop_station — each stop ID's station (stop IDs repeat across routes)
    3. final select — per alert × rail route × station: directions affected
#}

WITH

    -- 1. Every stop entry in each alert's latest version. Entries without a
    --    stop (route-wide) are skipped; a missing direction_id means both
    entities AS (
        SELECT
            a.alert_id,
            JSON_VALUE(entity, '$.route')                          AS route_id,
            JSON_VALUE(entity, '$.stop')                           AS stop_id,
            SAFE_CAST(JSON_VALUE(entity, '$.direction_id') AS INT64) AS direction_id,
            FALSE                                                  AS is_from_lamp
        FROM {{ ref('mbta_alerts__base') }} AS a
        CROSS JOIN UNNEST(JSON_QUERY_ARRAY(a.alert_json, '$.attributes.informed_entity')) AS entity
        WHERE JSON_VALUE(entity, '$.stop') IS NOT NULL

        UNION ALL

        -- LAMP alerts the JSON doesn't have
        SELECT
            a.alert_id,
            entity.route_id,
            entity.stop_id,
            entity.direction_id,
            TRUE AS is_from_lamp
        FROM {{ ref('lamp_alerts__base') }} AS a
        CROSS JOIN UNNEST(a.informed_entities) AS entity
        WHERE
            entity.stop_id IS NOT NULL
            AND a.alert_id NOT IN (SELECT captured.alert_id FROM {{ ref('mbta_alerts__base') }} AS captured)
    ),

    -- 2. Station per stop ID, whichever route it was listed under
    stop_station AS (
        SELECT DISTINCT
            stop_id,
            station_id
        FROM {{ ref('mbta_stops__base') }}
    )

-- 3. One row per alert × rail route × station. A stop in the live JSON that
--    the stops reference doesn't know yet keeps its own ID as station_id (the
--    relationships test flags it) rather than being dropped. Bus routes in
--    multi-mode alerts fall out at the routes join.
SELECT
    e.alert_id,
    e.route_id,
    COALESCE(s.station_id, e.stop_id)                                AS station_id,
    LOGICAL_OR(e.direction_id IS NULL) OR COUNT(DISTINCT e.direction_id) > 1 AS affects_both_directions,
    -- The one direction affected; NULL when both are
    IF(
        LOGICAL_OR(e.direction_id IS NULL) OR COUNT(DISTINCT e.direction_id) > 1,
        NULL,
        ANY_VALUE(e.direction_id)
    )                                                                AS direction_id
FROM entities AS e
INNER JOIN {{ ref('mbta_routes__base') }} AS r
    ON e.route_id = r.route_id
LEFT JOIN stop_station AS s
    ON e.stop_id = s.stop_id
-- LAMP stops that no longer exist (see header)
WHERE NOT (e.is_from_lamp AND s.station_id IS NULL)
GROUP BY
    e.alert_id,
    e.route_id,
    COALESCE(s.station_id, e.stop_id)
