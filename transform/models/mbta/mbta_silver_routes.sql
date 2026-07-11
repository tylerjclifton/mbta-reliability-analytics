{{-
    config(
        schema='mbta',
        alias='silver_routes',
        materialized='incremental',
        unique_key=['route_id'],
        on_schema_change='sync_all_columns'
    )
 -}}

SELECT
    CAST(route_id AS STRING)                AS route_id,
    CAST(long_name AS STRING)               AS route_name,
    CAST(description AS STRING)             AS route_description,
    CASE route_type
        WHEN 0 THEN 'Light Rail'
        WHEN 1 THEN 'Heavy Rail'
        ELSE CAST(route_type AS STRING)
    END                                     AS route_type,
    CAST(color AS STRING)                   AS route_color,
    CAST(direction_destinations AS STRING)  AS route_destinations,
    CAST(ingestion_timestamp AS TIMESTAMP)  AS ingestion_timestamp,
    CAST(ingestion_source AS STRING)        AS ingestion_source
FROM {{ ref('mbta_bronze_routes') }}
{% if is_incremental() %}
WHERE ingestion_timestamp >= (
    SELECT COALESCE(MAX(ingestion_timestamp), TIMESTAMP('1970-01-01'))
    FROM {{ this }}
)
{% endif %}
