{{-
    config(
        schema='nws',
        alias='silver_weather',
        materialized='incremental',
        unique_key=['observation_date'],
        on_schema_change='sync_all_columns'
    )
 -}}

SELECT
    DATE(observation_timestamp)         AS observation_date,
    AVG(temperature_fahrenheit)         AS avg_temperature_f,
    AVG(precipitation_last_hour_mm)     AS avg_precipitation_mm,
    AVG(wind_speed_mph)                 AS avg_wind_speed_mph,
    AVG(relative_humidity_percent)      AS avg_humidity_percent,
    MAX(ingestion_timestamp)            AS ingestion_timestamp,
    MAX(ingestion_source)               AS ingestion_source
FROM {{ ref('nws_bronze_weather') }}
{% if is_incremental() %}
WHERE ingestion_timestamp >= (
    SELECT COALESCE(MAX(ingestion_timestamp), TIMESTAMP('1970-01-01'))
    FROM {{ this }}
)
{% endif %}
GROUP BY DATE(observation_timestamp)
