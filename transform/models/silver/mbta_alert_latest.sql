{#
  silver.mbta_alert_latest — one row per alert × route

  The latest snapshot of every alert ever seen, plus when it was first and last
  seen. Everything about alerts downstream (silver.mbta_alerts, gold) reads this
  table instead of bronze.

  Why a table, not a view like the rest of silver: bronze.mbta_alerts gains a
  full snapshot every 15 minutes (~1 GB/year). A view would re-read that whole
  history for every model and test that uses it — about 9 times per hourly
  transform — which outgrows BigQuery's free query tier within a year. This
  table is incremental: each run reads only the snapshots added since the last
  run (a few KB), so the cost stays flat as history grows. Bronze remains the
  complete history; `dbt build --full-refresh` rebuilds this table from it.

  Steps:
    1. new_snapshots — bronze rows ingested after the latest one already here
    2. candidates    — those rows, plus the existing row for each alert they touch
    3. final select  — per alert × route: latest version's fields, earliest
                       first-seen, latest last-seen
#}

{{
    config(
        materialized='incremental',
        unique_key=['alert_id', 'route'],
        incremental_strategy='merge',
        cluster_by=['alert_id', 'route'],
        on_schema_change='append_new_columns'
    )
}}

{#- Alert fields carried from bronze (everything except the audit columns) -#}
{%- set alert_columns = [
    'alert_id', 'route', 'active_period_start', 'active_period_end', 'duration_certainty',
    'header', 'description', 'cause', 'effect', 'severity', 'created_at', 'updated_at',
] -%}

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
        FROM {{ source('bronze', 'mbta_alerts') }}
        {%- if processed_through %}
        WHERE ingested_at > TIMESTAMP '{{ processed_through }}'
        {%- endif %}
    ),

    -- 2. New snapshots, plus each touched alert's existing row (so first-seen
    --    survives the merge, which replaces the whole row)
    candidates AS (
        SELECT
            {{ alert_columns | join(',\n            ') }},
            ingested_at AS seen_at,
            ingested_at AS first_seen_at
        FROM new_snapshots
        {%- if is_incremental() %}

        UNION ALL

        SELECT
            {{ alert_columns | join(',\n            ') }},
            last_seen_at AS seen_at,
            first_seen_at
        FROM {{ this }}
        WHERE STRUCT(alert_id, route) IN (
            SELECT AS STRUCT
                alert_id,
                route
            FROM new_snapshots
        )
        {%- endif %}
    )

-- 3. Latest version per alert × route, with the full seen span
SELECT
    {{ alert_columns | join(',\n    ') }},
    MIN(first_seen_at) OVER alert AS first_seen_at,
    MAX(seen_at) OVER alert       AS last_seen_at
FROM candidates
QUALIFY ROW_NUMBER() OVER (PARTITION BY alert_id, route ORDER BY seen_at DESC) = 1
WINDOW alert AS (PARTITION BY alert_id, route)
