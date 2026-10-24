{#
  silver.mbta_alerts — one row per alert × route

  The latest snapshot of every alert ever seen in bronze.mbta_alerts, renamed
  to project conventions, plus when it was first and last seen. A cleaned copy
  of the source: no business rules (those start in silver.mbta_alerts__resolved).
  Enum values stay as the API sends them (e.g. SIGNAL_PROBLEM).

  Why a table, not a view like the other cleaned copies: bronze.mbta_alerts
  gains a full snapshot every 15 minutes (~1 GB/year). A view would re-read
  that whole history for every model and test that uses it — about 9 times per
  hourly transform — which outgrows BigQuery's free query tier within a year.
  This table is incremental: each run reads only the snapshots added since the
  last run (a few KB), so the cost stays flat as history grows. Bronze remains
  the complete history; `dbt build --full-refresh` rebuilds this table from it.

  Steps:
    1. new_snapshots — bronze rows ingested after the latest one already here,
                       renamed; the API's epoch placeholder becomes NULL
    2. candidates    — those rows, plus the existing row for each alert they touch
    3. final select  — per alert × route: latest version's fields, earliest
                       first-seen, latest last-seen
#}

{{
    config(
        materialized='incremental',
        unique_key=['alert_id', 'route_id'],
        incremental_strategy='merge',
        cluster_by=['alert_id', 'route_id'],
        on_schema_change='append_new_columns'
    )
}}

{#- Alert fields carried through (everything except the seen span) -#}
{%- set alert_columns = [
    'alert_id', 'route_id', 'posted_start_at', 'posted_end_at', 'alert_duration_certainty',
    'alert_header', 'alert_description', 'alert_cause', 'alert_effect', 'alert_severity',
    'alert_created_at', 'alert_updated_at',
] -%}

{#- The newest snapshot already processed, compiled into the query as a literal
    so BigQuery prunes bronze's ingested_at partitions (a subquery wouldn't) -#}
{%- set processed_through = none -%}
{%- if is_incremental() and execute -%}
    {%- set result = run_query("SELECT FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%E6S', MAX(last_seen_at)) FROM " ~ this) -%}
    {%- set processed_through = result.columns[0].values()[0] -%}
{%- endif %}

WITH

    -- 1. Snapshots not yet processed (all of bronze on the first run), renamed.
    --    The API uses the epoch (1970-01-01) for "not set"; treat it as NULL.
    new_snapshots AS (
        SELECT
            alert_id,
            route                                                                   AS route_id,
            IF(active_period_start > TIMESTAMP '1970-01-02', active_period_start, NULL) AS posted_start_at,
            IF(active_period_end   > TIMESTAMP '1970-01-02', active_period_end,   NULL) AS posted_end_at,
            duration_certainty                                                      AS alert_duration_certainty,
            header                                                                  AS alert_header,
            description                                                             AS alert_description,
            cause                                                                   AS alert_cause,
            effect                                                                  AS alert_effect,
            severity                                                                AS alert_severity,
            created_at                                                              AS alert_created_at,
            updated_at                                                              AS alert_updated_at,
            ingested_at
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
        WHERE STRUCT(alert_id, route_id) IN (
            SELECT AS STRUCT
                new_snapshots.alert_id,
                new_snapshots.route_id
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
QUALIFY ROW_NUMBER() OVER (PARTITION BY alert_id, route_id ORDER BY seen_at DESC) = 1
WINDOW alert AS (PARTITION BY alert_id, route_id)
