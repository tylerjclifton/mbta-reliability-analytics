{#
  silver.mbta_alerts__by_route — one row per alert × route

  silver.mbta_alerts__base split into one row per rail route its entities
  name, as silver.lamp_alerts__by_route splits LAMP's: the latest version of
  every alert seen since full-JSON capture began (2026-10-24), with when it
  was first and last seen. A reshaping step; no business rules yet (those
  start in silver.mbta_alerts__resolved).

  This is where the live feed is narrowed to rail: since 2026-10-28 bronze
  holds the whole feed (bus, commuter rail, ferry too; decision 0011), and an
  alert that names no rail route produces no rows here. Alerts the snapshots
  never saw come from the MBTA's LAMP archive instead
  (silver.lamp_alerts__by_route; decision 0016).

  A view: the base table already reads only new snapshots, and this splits it.
  Until 2026-11 it was its own incremental table over bronze, splitting every
  snapshot and keeping each route's own seen span; no alert in the 383
  alert × route rows since capture began had dropped a route in a later
  version, so the alert's span is each route's. If one does, that route's part
  of the alert ends with the alert rather than when it was dropped.

  Steps:
    1. final select — one row per alert × distinct rail route in its entities
#}

-- 1. One row per distinct route among the alert's entities, kept only for
--    rail routes: those in the routes table (the project's rail routes,
--    ingest/common/mbta_api.py), as in silver.mbta_alerts__by_station.
SELECT
    a.alert_id,
    rail.route_id,
    a.posted_start_at,
    a.posted_end_at,
    a.active_periods,
    a.alert_duration_certainty,
    a.alert_header,
    a.alert_description,
    a.alert_cause,
    a.alert_effect,
    a.alert_severity,
    a.alert_created_at,
    a.alert_updated_at,
    a.alert_closed_at,
    a.first_seen_at,
    a.last_seen_at
FROM {{ ref('mbta_alerts__base') }} AS a
CROSS JOIN UNNEST(ARRAY(
    SELECT DISTINCT entity.route_id
    FROM UNNEST(a.informed_entities) AS entity
)) AS entity_route_id
INNER JOIN {{ ref('mbta_routes__base') }} AS rail
    ON entity_route_id = rail.route_id
