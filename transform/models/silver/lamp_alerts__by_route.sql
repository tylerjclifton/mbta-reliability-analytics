{#
  silver.lamp_alerts__by_route — one row per LAMP alert × rail route

  silver.lamp_alerts__base split into one row per rail route its entities
  name, with the columns of silver.mbta_alerts__by_route plus the close time.
  A reshaping step with no business rules: silver.mbta_alerts__resolved takes
  from here the alerts that ended before full-JSON capture (decision 0016).

  Steps:
    1. final select — one row per alert × distinct rail route in its entities
#}

-- 1. One row per distinct route among the alert's entities, kept only for
--    rail routes (those in the routes table).
SELECT
    a.alert_id,
    rail.route_id,
    a.posted_start_at,
    a.posted_end_at,
    a.alert_duration_certainty,
    a.alert_header,
    a.alert_description,
    a.alert_cause,
    a.alert_effect,
    a.alert_severity,
    a.alert_created_at,
    a.alert_updated_at,
    a.alert_closed_at,
    a.ingested_at,
    a.ingested_by
FROM {{ ref('lamp_alerts__base') }} AS a
CROSS JOIN UNNEST(ARRAY(
    SELECT DISTINCT entity.route_id
    FROM UNNEST(a.informed_entities) AS entity
)) AS entity_route_id
INNER JOIN {{ ref('mbta_routes__base') }} AS rail
    ON entity_route_id = rail.route_id
