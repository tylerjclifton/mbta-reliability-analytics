{{-
    config(
        schema='gold',
        alias='mbta_alerts_with_weather',
        materialized='incremental',
        unique_key=['alert_id'],
        on_schema_change='sync_all_columns'
    )
 -}}

WITH
    base AS (
        SELECT *
        FROM {{ ref('mbta_silver') }}
{%- if is_incremental() %}
        WHERE ingestion_timestamp >= (
            SELECT COALESCE(MAX(ingestion_timestamp), TIMESTAMP('1970-01-01'))
            FROM {{ this }}
        )
{%- endif %}
    ),

    weather_agg AS (
        SELECT
            DATE(observation_timestamp) AS observation_date,
            AVG(temperature_fahrenheit) AS avg_temperature_f,
            MIN(temperature_fahrenheit) AS min_temperature_f,
            MAX(temperature_fahrenheit) AS max_temperature_f,
            AVG(precipitation_last_hour_mm) AS avg_precipitation_mm,
            MAX(precipitation_last_hour_mm) AS max_precipitation_mm,
            AVG(wind_speed_mph) AS avg_wind_speed_mph,
            MAX(wind_speed_mph) AS max_wind_speed_mph,
            AVG(visibility_miles) AS avg_visibility_miles,
            MIN(visibility_miles) AS min_visibility_miles,
            AVG(relative_humidity_percent) AS avg_humidity_percent
        FROM {{ ref('nws_silver') }}
        GROUP BY DATE(observation_timestamp)
    )

SELECT
    base.*,
    weather_agg.avg_temperature_f,
    weather_agg.min_temperature_f,
    weather_agg.max_temperature_f,
    weather_agg.avg_precipitation_mm,
    weather_agg.max_precipitation_mm,
    weather_agg.avg_wind_speed_mph,
    weather_agg.max_wind_speed_mph,
    weather_agg.avg_visibility_miles,
    weather_agg.min_visibility_miles,
    weather_agg.avg_humidity_percent
FROM base
LEFT JOIN weather_agg
    ON base.alert_start_date = weather_agg.observation_date
