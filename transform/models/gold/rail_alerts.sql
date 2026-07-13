{{-
    config(
        schema='gold',
        alias='rail_alerts',
        materialized='view'
    )
 -}}

SELECT
    a.alert_id,
    a.route_id,
    a.alert_start_date,
    a.alert_end_date,
    a.alert_header,
    a.alert_description,
    a.alert_cause,
    a.alert_effect,
    a.alert_severity,
    a.alert_duration_certainty,
    a.alert_created_at,
    a.alert_updated_at,
    a.alert_duration_minutes,
    r.route_name,
    r.route_description,
    r.route_type,
    r.route_color,
    r.route_destinations,
    a.ingestion_timestamp,
    a.ingestion_source
FROM {{ ref('mbta_silver_alerts') }} a
LEFT JOIN {{ ref('mbta_silver_routes') }} r
    ON a.route_id = r.route_id
