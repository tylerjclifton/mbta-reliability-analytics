{#
  gold.rail_alerts — one row per alert × route

  Individual alerts enriched with route metadata — the alert-level detail
  behind gold.rail_incidents (which the dashboard reads).

  Steps:
    1. final select — silver alerts LEFT JOIN silver routes on route_id
#}

-- 1. Alerts with their route's name, line, and type
SELECT
    a.alert_id,
    a.route_id,
    a.incident_id,
    r.route_name,
    r.line_name,
    r.route_type,
    a.alert_header,
    a.alert_description,
    a.alert_cause,
    a.alert_effect,
    a.alert_severity,
    a.alert_duration_certainty,
    a.alert_start_at,
    a.alert_end_at,
    a.alert_start_date,
    a.alert_end_date,
    a.alert_duration_minutes,
    a.alert_created_at,
    a.alert_updated_at,
    a.is_in_feed,
    a.ingested_at
FROM {{ ref('mbta_alerts') }} AS a
LEFT JOIN {{ ref('mbta_routes') }} AS r
    ON a.route_id = r.route_id
