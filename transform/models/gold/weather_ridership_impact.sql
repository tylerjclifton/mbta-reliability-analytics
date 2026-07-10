{{-
    config(
        schema='gold',
        alias='weather_ridership_impact',
        materialized='view'
    )
 -}}

SELECT
    r.service_date,
    r.route_name,
    r.ridership,
    w.avg_temperature_f,
    w.avg_precipitation_mm,
    w.avg_wind_speed_mph,
    w.avg_humidity_percent
FROM {{ ref('mbta_silver_ridership') }} r
LEFT JOIN {{ ref('nws_silver_weather') }} w
    ON r.service_date = w.observation_date
