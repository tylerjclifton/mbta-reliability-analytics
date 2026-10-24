{#
  silver.mbta_alerts_raw — one row per alert

  The latest full JSON of every alert in bronze.mbta_alerts_raw, plus when it
  was first and last seen. A cleaned copy of the source: models that need what
  bronze.mbta_alerts drops (the stops an alert affects, see
  silver.alert_stations) read this table.

  Incremental for the same reason as silver.mbta_alerts: the raw table
  gains a full snapshot every 15 minutes (~2.6 GB/year), and a view would
  re-read all of it on every transform. Each run reads only the snapshots added
  since the last one; `dbt build --full-refresh` rebuilds it from bronze.

  Raw capture started 2026-10-24, so alerts that ended before then aren't here.

  Steps:
    1. new_snapshots — bronze rows ingested after the latest one already here
    2. candidates    — those rows, plus the existing row for each alert they touch
    3. final select  — per alert: latest JSON, earliest first-seen, latest last-seen
#}

{{
    config(
        materialized='incremental',
        unique_key='alert_id',
        incremental_strategy='merge',
        cluster_by=['alert_id'],
        on_schema_change='append_new_columns'
    )
}}

{#- The newest snapshot already processed, compiled into the query as a literal
    so BigQuery prunes bronze's ingested_at partitions (a subquery wouldn't) -#}
{%- set processed_through = none -%}
{%- if is_incremental() and execute -%}
    {%- set result = run_query("SELECT FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%E6S', MAX(last_seen_at)) FROM " ~ this) -%}
    {%- set processed_through = result.columns[0].values()[0] -%}
{%- endif %}

WITH

    -- 1. Snapshots not yet processed (all of bronze on the first run)
    new_snapshots AS (
        SELECT *
        FROM {{ source('bronze', 'mbta_alerts_raw') }}
        {%- if processed_through %}
        WHERE ingested_at > TIMESTAMP '{{ processed_through }}'
        {%- endif %}
    ),

    -- 2. New snapshots, plus each touched alert's existing row (so first-seen
    --    survives the merge, which replaces the whole row)
    candidates AS (
        SELECT
            alert_id,
            alert_json,
            ingested_at AS seen_at,
            ingested_at AS first_seen_at
        FROM new_snapshots
        {%- if is_incremental() %}

        UNION ALL

        SELECT
            alert_id,
            alert_json,
            last_seen_at AS seen_at,
            first_seen_at
        FROM {{ this }}
        WHERE alert_id IN (SELECT new_snapshots.alert_id FROM new_snapshots)
        {%- endif %}
    )

-- 3. Latest version per alert, with the full seen span
SELECT
    alert_id,
    alert_json,
    MIN(first_seen_at) OVER alert AS first_seen_at,
    MAX(seen_at) OVER alert       AS last_seen_at
FROM candidates
QUALIFY ROW_NUMBER() OVER (PARTITION BY alert_id ORDER BY seen_at DESC) = 1
WINDOW alert AS (PARTITION BY alert_id)
