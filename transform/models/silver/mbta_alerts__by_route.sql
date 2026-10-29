{#
  silver.mbta_alerts__by_route — one row per alert × route

  The latest snapshot of every alert ever seen, split into one row per rail
  route and renamed to project conventions, plus when it was first and last
  seen. A reshaping step, with history from the frozen table stitched in; no
  business rules yet (those start in silver.mbta_alerts__resolved). Enum
  values stay as the API sends them (e.g. SIGNAL_PROBLEM).

  Two bronze tables feed it, split at var alerts_raw_capture_start
  (2026-10-24 14:11 UTC):
    - before it, bronze.mbta_alerts_legacy: the frozen shaped table, which the ingest
      wrote directly at alert × route grain
    - from it on, bronze.mbta_alerts: each alert's full JSON, split here
      into one row per rail route with the same rules the ingest used (one row
      per target route in informed_entity; the first active period). Both
      tables were written from the capture start until the cutover and
      matched row for row (decision 0002).

  This is where alerts are narrowed to rail: since 2026-10-28 bronze holds the
  whole feed (bus, commuter rail, ferry too; decision 0011), and an alert that
  names no rail route produces no rows here.

  Why a table, not a view like most of silver: alert snapshots arrive
  every 15 minutes (~15 GB/year of JSON). A view would re-read that whole
  history for every model and test that uses it — about 9 times per hourly
  transform — which outgrows BigQuery's free query tier within a year. This
  table is incremental: each run reads only the snapshots added since the last
  run, and once past the capture start never reads the frozen table again.
  Bronze remains the complete history; `dbt build --full-refresh` rebuilds this
  table from it.

  Steps:
    1. new_snapshots — snapshots after the latest one already here: frozen
                       shaped rows before the capture start, full JSON split per
                       route from it on; the API's epoch placeholder → NULL
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

{%- set capture_start = var('alerts_raw_capture_start') -%}

{#- The newest snapshot already processed (none on a first build), compiled
    in as a literal so bronze's partitions are pruned -#}
{%- set processed_through = last_processed_snapshot() -%}

{#- The frozen table only holds snapshots before the capture start, so skip it
    entirely once this table has processed past it (both strings share one
    timestamp format, so they compare correctly as text) -#}
{%- set read_frozen = processed_through is none or processed_through < capture_start %}

WITH

    -- 1. Snapshots not yet processed, renamed. The API uses the epoch
    --    (1970-01-01) for "not set"; treat it as NULL.
    new_snapshots AS (
        {%- if read_frozen %}
        -- Before the capture start: the frozen shaped table
        SELECT
            alert_id,
            route                                      AS route_id,
            {{ null_if_epoch('active_period_start') }} AS posted_start_at,
            {{ null_if_epoch('active_period_end') }}   AS posted_end_at,
            duration_certainty                         AS alert_duration_certainty,
            header                                     AS alert_header,
            description                                AS alert_description,
            cause                                      AS alert_cause,
            effect                                     AS alert_effect,
            severity                                   AS alert_severity,
            created_at                                 AS alert_created_at,
            updated_at                                 AS alert_updated_at,
            ingested_at
        FROM {{ source('bronze', 'mbta_alerts_legacy') }}
        WHERE
            ingested_at < TIMESTAMP '{{ capture_start }}'
            {%- if processed_through %}
            AND ingested_at > TIMESTAMP '{{ processed_through }}'
            {%- endif %}

        UNION ALL
        {%- endif %}

        -- From the capture start on: full JSON, one row per rail route it names
        SELECT
            alert_id,
            route_id,
            {{ null_if_epoch('posted_start_at') }} AS posted_start_at,
            {{ null_if_epoch('posted_end_at') }}   AS posted_end_at,
            alert_duration_certainty,
            alert_header,
            alert_description,
            alert_cause,
            alert_effect,
            alert_severity,
            alert_created_at,
            alert_updated_at,
            ingested_at
        FROM (
            SELECT
                r.alert_id,
                rail.route_id,
                -- Only the first active period, as the shaped table kept
                TIMESTAMP(JSON_VALUE(r.alert_json, '$.attributes.active_period[0].start')) AS posted_start_at,
                TIMESTAMP(JSON_VALUE(r.alert_json, '$.attributes.active_period[0].end'))   AS posted_end_at,
                JSON_VALUE(r.alert_json, '$.attributes.duration_certainty')                AS alert_duration_certainty,
                JSON_VALUE(r.alert_json, '$.attributes.header')                            AS alert_header,
                JSON_VALUE(r.alert_json, '$.attributes.description')                       AS alert_description,
                JSON_VALUE(r.alert_json, '$.attributes.cause')                             AS alert_cause,
                JSON_VALUE(r.alert_json, '$.attributes.effect')                            AS alert_effect,
                SAFE_CAST(JSON_VALUE(r.alert_json, '$.attributes.severity') AS INT64)      AS alert_severity,
                TIMESTAMP(JSON_VALUE(r.alert_json, '$.attributes.created_at'))             AS alert_created_at,
                TIMESTAMP(JSON_VALUE(r.alert_json, '$.attributes.updated_at'))             AS alert_updated_at,
                r.ingested_at
            FROM {{ source('bronze', 'mbta_alerts') }} AS r
            -- One row per distinct route among the alert's informed entities...
            CROSS JOIN UNNEST(ARRAY(
                SELECT DISTINCT JSON_VALUE(entity, '$.route')
                FROM UNNEST(JSON_QUERY_ARRAY(r.alert_json, '$.attributes.informed_entity')) AS entity
            )) AS entity_route_id
            -- ...kept only for rail routes: those in the routes table (the
            -- project's rail routes, ingest/common/mbta_api.py), as in
            -- mbta_alerts__by_station
            INNER JOIN {{ ref('mbta_routes__base') }} AS rail
                ON entity_route_id = rail.route_id
            WHERE
                r.ingested_at >= TIMESTAMP '{{ capture_start }}'
                {%- if processed_through %}
                AND r.ingested_at > TIMESTAMP '{{ processed_through }}'
                {%- endif %}
        ) AS raw_split
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
