{{-
    config(
        schema='gold',
        alias='rail_ridership',
        materialized='view'
    )
 -}}

WITH

    -- Normalize alert route_id to line-level names matching ridership route_name.
    -- Green branches (Green-B/C/D/E) all map to 'Green Line'.
    -- COUNT(DISTINCT alert_id) ensures a multi-branch alert counts as one per line.
    alert_counts AS (
        SELECT
            CASE
                WHEN route_id = 'Red'                    THEN 'Red Line'
                WHEN route_id = 'Orange'                 THEN 'Orange Line'
                WHEN route_id = 'Blue'                   THEN 'Blue Line'
                WHEN STARTS_WITH(route_id, 'Green')      THEN 'Green Line'
            END                                          AS route_name,
            alert_start_date,
            alert_end_date,
            alert_id
        FROM {{ ref('mbta_silver_alerts') }}
        WHERE alert_start_date IS NOT NULL
    )

SELECT
    r.service_date,
    r.route_name,
    r.ridership,
    COUNT(DISTINCT a.alert_id)  AS line_alert_count,
    w.avg_temperature_f,
    w.max_temperature_f,
    w.total_precipitation_mm,
    w.avg_wind_speed_mph,
    w.avg_humidity_percent,
    w.min_visibility_miles
FROM {{ ref('mbta_silver_ridership') }} r
LEFT JOIN alert_counts a
    ON  r.route_name = a.route_name
    AND r.service_date BETWEEN a.alert_start_date
        AND COALESCE(a.alert_end_date, CURRENT_DATE())
LEFT JOIN {{ ref('nws_silver_weather') }} w
    ON r.service_date = w.observation_date
GROUP BY
    r.service_date,
    r.route_name,
    r.ridership,
    w.avg_temperature_f,
    w.max_temperature_f,
    w.total_precipitation_mm,
    w.avg_wind_speed_mph,
    w.avg_humidity_percent,
    w.min_visibility_miles
