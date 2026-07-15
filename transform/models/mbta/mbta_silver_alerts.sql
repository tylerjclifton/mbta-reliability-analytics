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

    -- Current live snapshot of alerts from the MBTA API (WRITE_TRUNCATE each ingest run).
    -- Used to determine whether an open alert is still active or has silently ended.
    staging_active AS (
        SELECT DISTINCT alert_id, route
        FROM `{{ target.project }}.stage.mbta_alerts`
    ),

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
        -- Also reprocess any currently open alerts so they can be re-evaluated
        -- against staging on every run (catches alerts that silently ended).
        OR alert_id IN (
            SELECT alert_id FROM {{ this }} WHERE alert_end_date IS NULL
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
    ),

    resolved AS (
        SELECT
            c.*,
            -- Epoch (1970-01-01 UTC) on start means no real start was set; fall back to created_at
            CASE
                WHEN c.alert_start_ts IS NULL
                     OR DATE(DATETIME(c.alert_start_ts, 'America/New_York')) = DATE('1969-12-31')
                    THEN TIMESTAMP(c.alert_created_at, 'America/New_York')
                ELSE c.alert_start_ts
            END AS resolved_start_ts,
            CASE
                -- Explicit end timestamp provided by the API → use it as-is
                -- Epoch (1970-01-01 UTC) is treated as NULL — it means no real end was set
                WHEN c.alert_end_ts IS NOT NULL
                     AND DATE(DATETIME(c.alert_end_ts, 'America/New_York')) != DATE('1969-12-31')
                    THEN c.alert_end_ts
                -- Alert is still present in staging → genuinely ongoing
                WHEN sa.alert_id IS NOT NULL
                    THEN NULL
                -- Alert has disappeared from staging with no explicit end →
                -- infer end as last ingestion timestamp + 30 minutes
                ELSE TIMESTAMP_ADD(c.ingestion_timestamp, INTERVAL 30 MINUTE)
            END AS resolved_end_ts
        FROM converted c
        LEFT JOIN staging_active sa
            ON  c.alert_id  = sa.alert_id
            AND c.route_id  = sa.route
    )

SELECT
    alert_id,
    route_id,
    -- Null/epoch guard: replace NULL or epoch (1969-12-31 ET) with alert_created_at as fallback
    COALESCE(
        NULLIF(alert_start_date_et, DATE('1969-12-31')),
        alert_created_at
    )                                                    AS alert_start_date,
    -- Ongoing alerts stay NULL; resolved alerts use the resolved end timestamp
    CASE
        WHEN resolved_end_ts IS NULL THEN NULL
        ELSE NULLIF(DATE(DATETIME(resolved_end_ts, 'America/New_York')), DATE('1969-12-31'))
    END                                                  AS alert_end_date,
    alert_header,
    alert_description,
    INITCAP(REPLACE(alert_cause, '_', ' '))              AS alert_cause,
    INITCAP(REPLACE(alert_effect, '_', ' '))             AS alert_effect,
    alert_severity,
    INITCAP(REPLACE(alert_duration_certainty, '_', ' ')) AS alert_duration_certainty,
    alert_created_at,
    alert_updated_at,
    -- Duration uses resolved start/end; ongoing alerts fall back to current time
    TIMESTAMP_DIFF(
        COALESCE(resolved_end_ts, CURRENT_TIMESTAMP()),
        resolved_start_ts,
        MINUTE
    ) AS alert_duration_minutes,
    ingestion_timestamp,
    ingestion_source
FROM resolved
