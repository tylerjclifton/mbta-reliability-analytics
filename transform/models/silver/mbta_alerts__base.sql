{#
  silver.mbta_alerts__base — one row per alert

  The latest version of every alert in bronze.mbta_alerts, every mode, plus
  when it was first and last seen. A cleaned copy of the source: its JSON is
  parsed here, once, into the same typed columns silver.lamp_alerts__base has
  (enum values stay as the API sends them, e.g. SIGNAL_PROBLEM), and kept
  whole for fields no model reads yet. Every alert model reads the live feed
  from here.

  Incremental: bronze.mbta_alerts gains a full snapshot every 15 minutes, and
  a view would re-read all of it on every transform, outgrowing BigQuery's free
  query tier within a year (decision 0010). Each run reads only the snapshots
  added since the last one; `dbt build --full-refresh` rebuilds it from
  bronze, and is needed after adding a column, since existing rows would
  otherwise leave it empty.

  Full-JSON capture started 2026-10-24, so alerts that ended before then
  aren't here; nor are short alerts that closed between two runs. Both come
  from the MBTA's LAMP archive instead (decision 0016).

  Steps:
    1. new_snapshots — bronze rows ingested after the latest one already here
    2. candidates    — those rows, plus the existing row for each alert they
                       touch
    3. latest        — per alert: latest JSON, earliest first-seen, latest
                       last-seen
    4. periods       — its active periods, earliest first
    5. final select  — the JSON's fields, typed
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

{#- The newest snapshot already processed (none on a first build), compiled
    in as a literal so bronze's partitions are pruned. -#}
{%- set processed_through = last_processed_snapshot() %}

WITH

    -- 1. Snapshots not yet processed (all of bronze on the first run).
    new_snapshots AS (
        SELECT *
        FROM {{ source('bronze', 'mbta_alerts') }}
        {%- if processed_through %}
        WHERE ingested_at > TIMESTAMP '{{ processed_through }}'
        {%- endif %}
    ),

    -- 2. New snapshots, plus each touched alert's existing row (so first-seen
    --    survives the merge, which replaces the whole row).
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
    ),

    -- 3. Latest version per alert, with the full seen span.
    latest AS (
        SELECT
            alert_id,
            alert_json,
            MIN(first_seen_at) OVER alert AS first_seen_at,
            MAX(seen_at) OVER alert       AS last_seen_at
        FROM candidates
        QUALIFY ROW_NUMBER() OVER (PARTITION BY alert_id ORDER BY seen_at DESC) = 1
        WINDOW alert AS (PARTITION BY alert_id)
    ),

    -- 4. Its active periods, earliest first. The API sends the epoch for an
    --    unset time; a period with no start is left out, as in LAMP.
    periods AS (
        SELECT
            alert_id,
            ARRAY(
                SELECT AS STRUCT
                    {{ null_if_epoch("TIMESTAMP(JSON_VALUE(period, '$.start'))") }} AS start_at,
                    {{ null_if_epoch("TIMESTAMP(JSON_VALUE(period, '$.end'))") }}   AS end_at
                FROM UNNEST(JSON_QUERY_ARRAY(alert_json, '$.attributes.active_period')) AS period
                WHERE {{ null_if_epoch("TIMESTAMP(JSON_VALUE(period, '$.start'))") }} IS NOT NULL
                ORDER BY start_at
            ) AS active_periods
        FROM latest
    )

-- 5. One row per alert: the JSON's fields typed, the JSON itself, and the
--    seen span.
SELECT
    l.alert_id,
    JSON_VALUE(l.alert_json, '$.attributes.header')                       AS alert_header,
    JSON_VALUE(l.alert_json, '$.attributes.description')                  AS alert_description,
    JSON_VALUE(l.alert_json, '$.attributes.cause')                        AS alert_cause,
    JSON_VALUE(l.alert_json, '$.attributes.effect')                       AS alert_effect,
    SAFE_CAST(JSON_VALUE(l.alert_json, '$.attributes.severity') AS INT64) AS alert_severity,
    JSON_VALUE(l.alert_json, '$.attributes.duration_certainty')           AS alert_duration_certainty,
    p.active_periods[SAFE_OFFSET(0)].start_at                             AS posted_start_at,
    p.active_periods[SAFE_OFFSET(0)].end_at                               AS posted_end_at,
    p.active_periods,
    TIMESTAMP(JSON_VALUE(l.alert_json, '$.attributes.created_at'))        AS alert_created_at,
    TIMESTAMP(JSON_VALUE(l.alert_json, '$.attributes.updated_at'))        AS alert_updated_at,
    -- Set once the MBTA closes the alert; it stays
    -- in the feed a few minutes after.
    TIMESTAMP(JSON_VALUE(l.alert_json, '$.attributes.closed_timestamp'))  AS alert_closed_at,
    -- Every entity's route, stop, and direction (a missing direction means
    -- both), each once.
    ARRAY(
        SELECT DISTINCT AS STRUCT
            JSON_VALUE(entity, '$.route')                            AS route_id,
            JSON_VALUE(entity, '$.stop')                             AS stop_id,
            SAFE_CAST(JSON_VALUE(entity, '$.direction_id') AS INT64) AS direction_id
        FROM UNNEST(JSON_QUERY_ARRAY(l.alert_json, '$.attributes.informed_entity')) AS entity
    )                                                                     AS informed_entities,
    l.alert_json,
    l.first_seen_at,
    l.last_seen_at
FROM latest AS l
INNER JOIN periods AS p
    ON l.alert_id = p.alert_id
