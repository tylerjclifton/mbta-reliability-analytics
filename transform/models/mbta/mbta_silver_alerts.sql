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
            CAST(alert_id AS STRING)               AS alert_id,
            CAST(route AS STRING)                  AS route_id,
            CAST(active_period_start AS TIMESTAMP) AS alert_start_ts,
            CAST(active_period_end AS TIMESTAMP)   AS alert_end_ts,
            CAST(header AS STRING)                 AS alert_header,
            CAST(description AS STRING)            AS alert_description,
            CAST(cause AS STRING)                  AS alert_cause,
            CAST(effect AS STRING)                 AS alert_effect,
            CAST(severity AS INT64)                AS alert_severity,
            CAST(duration_certainty AS STRING)     AS alert_duration_certainty,
            DATE(DATETIME(CAST(created_at AS TIMESTAMP), 'America/New_York')) AS alert_created_at,
            DATE(DATETIME(CAST(updated_at AS TIMESTAMP), 'America/New_York')) AS alert_updated_at,
            CAST(ingestion_timestamp AS TIMESTAMP) AS ingestion_timestamp,
            CAST(ingestion_source AS STRING)       AS ingestion_source
        FROM {{ ref('mbta_bronze_alerts') }}
        {% if is_incremental() %}
        WHERE ingestion_timestamp >= (
            SELECT COALESCE(MAX(ingestion_timestamp), TIMESTAMP('1970-01-01'))
            FROM {{ this }}
        )
        {% endif %}
        QUALIFY ROW_NUMBER() OVER (PARTITION BY alert_id, route ORDER BY ingestion_timestamp DESC) = 1
    ),

    converted AS (
        SELECT
            alert_id,
            route_id,
            alert_start_ts,
            alert_end_ts,
            -- Convert UTC timestamps to ET dates (fixes cross-midnight UTC artifacts)
            DATE(DATETIME(alert_start_ts, 'America/New_York')) AS alert_start_date_et,
            DATE(DATETIME(alert_end_ts,   'America/New_York')) AS alert_end_date_et,
            alert_header,
            alert_description,
            alert_cause,
            alert_effect,
            alert_severity,
            alert_duration_certainty,
            alert_created_at,
            alert_updated_at,
            ingestion_timestamp,
            ingestion_source
        FROM base
    )

SELECT
    alert_id,
    route_id,
    -- Null/epoch guard: replace NULL or epoch (1969-12-31 ET) with alert_created_at as fallback
    COALESCE(
        NULLIF(alert_start_date_et, DATE('1969-12-31')),
        alert_created_at
    )                                                    AS alert_start_date,
    -- Null/epoch guard: epoch or NULL = ongoing (keep as NULL)
    NULLIF(alert_end_date_et, DATE('1969-12-31'))        AS alert_end_date,
    alert_header,
    alert_description,
    INITCAP(REPLACE(alert_cause, '_', ' '))              AS alert_cause,
    INITCAP(REPLACE(alert_effect, '_', ' '))             AS alert_effect,
    alert_severity,
    INITCAP(REPLACE(alert_duration_certainty, '_', ' ')) AS alert_duration_certainty,
    alert_created_at,
    alert_updated_at,
    -- Duration in minutes from raw timestamps (accurate, timezone-independent)
    -- Null end timestamp = ongoing; defaults to current time
    TIMESTAMP_DIFF(
        COALESCE(alert_end_ts, CURRENT_TIMESTAMP()),
        alert_start_ts,
        MINUTE
    ) AS alert_duration_minutes,
    ingestion_timestamp,
    ingestion_source
FROM converted
