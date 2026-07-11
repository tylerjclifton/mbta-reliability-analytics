{{-
    config(
        schema='mbta',
        alias='silver_alerts',
        materialized='incremental',
        unique_key=['alert_id', 'route_id'],
        on_schema_change='sync_all_columns'
    )
 -}}

WITH

    base AS (
        SELECT
            CAST(alert_id AS STRING)                AS alert_id,
            CAST(route AS STRING)                   AS route_id,
            {{ cast_as_date('active_period_start') }} AS alert_start_date,
            {{ cast_as_date('active_period_end') }}   AS alert_end_date,
            CAST(header AS STRING)                  AS alert_header,
            CAST(description AS STRING)             AS alert_description,
            CAST(cause AS STRING)                   AS alert_cause,
            CAST(effect AS STRING)                  AS alert_effect,
            CAST(severity AS INT64)                 AS alert_severity,
            CAST(duration_certainty AS STRING)      AS alert_duration_certainty,
            {{ cast_as_date('created_at') }}          AS alert_created_at,
            {{ cast_as_date('updated_at') }}          AS alert_updated_at,
            CAST(ingestion_timestamp AS TIMESTAMP)  AS ingestion_timestamp,
            CAST(ingestion_source AS STRING)        AS ingestion_source
        FROM {{ ref('mbta_bronze_alerts') }}
        {% if is_incremental() %}
        WHERE ingestion_timestamp >= (
            SELECT COALESCE(MAX(ingestion_timestamp), TIMESTAMP('1970-01-01'))
            FROM {{ this }}
        )
        {% endif %}
        QUALIFY ROW_NUMBER() OVER (PARTITION BY alert_id, route ORDER BY ingestion_timestamp DESC) = 1
    )

SELECT
    alert_id,
    route_id,
    alert_start_date,
    alert_end_date,
    alert_header,
    alert_description,
    INITCAP(REPLACE(alert_cause, '_', ' '))              AS alert_cause,
    INITCAP(REPLACE(alert_effect, '_', ' '))             AS alert_effect,
    alert_severity,
    INITCAP(REPLACE(alert_duration_certainty, '_', ' ')) AS alert_duration_certainty,
    alert_created_at,
    alert_updated_at,
    -- Duration in days, minimum 1. Epoch start (1970-01-01) falls back to created date.
    -- Null end date defaults to today for ongoing alerts.
    GREATEST(1, DATE_DIFF(
        COALESCE(alert_end_date, CURRENT_DATE()),
        CASE WHEN alert_start_date = DATE('1970-01-01') THEN alert_created_at ELSE alert_start_date END,
        DAY
    ) + 1) AS alert_duration_days,
    ingestion_timestamp,
    ingestion_source
FROM base
