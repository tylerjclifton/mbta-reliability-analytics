{#
  silver.lamp_alerts__base — one row per rail alert

  The latest version of every alert in bronze.lamp_alerts (the MBTA's LAMP
  archive) that names a project rail route, in project conventions: LAMP's MBTA
  enums (cause_detail, effect_detail) become alert_cause and alert_effect, the
  API's names for them; epoch seconds become timestamps; and the version's rows
  (one per informed entity × active period) collapse to its entity list and
  first active period, as silver.mbta_alerts__by_route reads the API's. Alerts
  from before full-JSON capture come from here (decision 0016).

  Narrowed to rail here, unlike silver.mbta_alerts__base: LAMP holds every mode
  back to 2018, and the views built on this read it on every transform.

  A version never changes once posted, so its rows repeat in every load (and a
  load that failed partway repeats some of them); DISTINCT drops the repeats.

  Incremental: a run with no new load since the last reads nothing (bronze's
  partitions are pruned). A new load rebuilds every alert from all of bronze,
  so a version split across a failed load and a complete one is never read
  half-loaded. `dbt build --full-refresh` does the same.

  Steps:
    1. versions     — distinct LAMP rows, renamed (none
                      unless there's a new load)
    2. loads        — the latest load, stamped on every row
    3. latest       — each alert's latest version, flagged if a row names a
                      rail route
    4. entities     — each latest version's distinct informed entities
    5. final select — per alert: that version's fields, entities, and first
                      active period; rail alerts only
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

{#- The newest load already processed (none on a first build). -#}
{%- set processed_through = last_processed_snapshot('ingested_at') -%}

{#- Whether bronze holds a load this table hasn't processed. Counting rows in
    the partitions after it reads next to nothing. -#}
{%- set has_new_load = true -%}
{%- if processed_through and execute -%}
    {%- set new_rows = run_query(
        "SELECT COUNT(*) FROM " ~ source('bronze', 'lamp_alerts')
        ~ " WHERE ingested_at > TIMESTAMP '" ~ processed_through ~ "'"
    ) -%}
    {%- set has_new_load = new_rows.columns[0].values()[0] > 0 -%}
{%- endif -%}

{#- With no new load, read only the partitions after the last one: none. -#}
{%- set no_new_rows = "WHERE ingested_at > TIMESTAMP '" ~ processed_through ~ "'" if not has_new_load else '' %}

WITH

    -- 1. Every distinct row across loads, renamed.
    versions AS (
        SELECT DISTINCT
            CAST(id AS STRING)                               AS alert_id,
            last_modified_timestamp,
            header_text                                      AS alert_header,
            description_text                                 AS alert_description,
            cause_detail                                     AS alert_cause,
            effect_detail                                    AS alert_effect,
            severity                                         AS alert_severity,
            duration_certainty                               AS alert_duration_certainty,
            TIMESTAMP_SECONDS(created_timestamp)             AS alert_created_at,
            TIMESTAMP_SECONDS(last_modified_timestamp)       AS alert_updated_at,
            TIMESTAMP_SECONDS(closed_timestamp)              AS alert_closed_at,
            TIMESTAMP_SECONDS(active_period_start_timestamp) AS period_start_at,
            TIMESTAMP_SECONDS(active_period_end_timestamp)   AS period_end_at,
            informed_entity_route_id                         AS route_id,
            informed_entity_stop_id                          AS stop_id,
            informed_entity_direction_id                     AS direction_id
        FROM {{ source('bronze', 'lamp_alerts') }}
        {{ no_new_rows }}
    ),

    -- 2. The latest load (silver's incremental marker) and its job.
    loads AS (
        SELECT
            MAX(ingested_at)        AS ingested_at,
            ANY_VALUE(ingested_by)  AS ingested_by
        FROM {{ source('bronze', 'lamp_alerts') }}
        {{ no_new_rows }}
    ),

    -- 3. Each alert's latest version, and whether each row names a rail route
    --    (those in the routes table, as in silver.mbta_alerts__by_route).
    latest AS (
        SELECT
            v.*,
            rail.route_id IS NOT NULL AS is_rail_route
        FROM versions AS v
        LEFT JOIN {{ ref('mbta_routes__base') }} AS rail
            ON v.route_id = rail.route_id
        QUALIFY v.last_modified_timestamp = MAX(v.last_modified_timestamp) OVER (PARTITION BY v.alert_id)
    ),

    -- 4. Each version repeats an entity once per active period; keep one.
    entities AS (
        SELECT
            alert_id,
            ARRAY_AGG(STRUCT(route_id, stop_id, direction_id)) AS informed_entities
        FROM (
            SELECT DISTINCT
                alert_id,
                route_id,
                stop_id,
                direction_id
            FROM latest
        ) AS distinct_entities
        GROUP BY alert_id
    )

-- 5. One row per alert. A version's fields repeat on each of its rows. Its
--    first active period is the earliest-starting one.
SELECT
    l.alert_id,
    ANY_VALUE(l.alert_header)                                  AS alert_header,
    ANY_VALUE(l.alert_description)                             AS alert_description,
    ANY_VALUE(l.alert_cause)                                   AS alert_cause,
    ANY_VALUE(l.alert_effect)                                  AS alert_effect,
    ANY_VALUE(l.alert_severity)                                AS alert_severity,
    ANY_VALUE(l.alert_duration_certainty)                      AS alert_duration_certainty,
    ARRAY_AGG(
        STRUCT(l.period_start_at AS start_at, l.period_end_at AS end_at)
        ORDER BY COALESCE(l.period_start_at, TIMESTAMP '9999-12-31') LIMIT 1
    )[OFFSET(0)].start_at                                      AS posted_start_at,
    ARRAY_AGG(
        STRUCT(l.period_start_at AS start_at, l.period_end_at AS end_at)
        ORDER BY COALESCE(l.period_start_at, TIMESTAMP '9999-12-31') LIMIT 1
    )[OFFSET(0)].end_at                                        AS posted_end_at,
    ANY_VALUE(l.alert_created_at)                              AS alert_created_at,
    ANY_VALUE(l.alert_updated_at)                              AS alert_updated_at,
    ANY_VALUE(l.alert_closed_at)                               AS alert_closed_at,
    ANY_VALUE(e.informed_entities)                             AS informed_entities,
    ANY_VALUE(loads.ingested_at)                               AS ingested_at,
    ANY_VALUE(loads.ingested_by)                               AS ingested_by
FROM latest AS l
INNER JOIN entities AS e
    ON l.alert_id = e.alert_id
CROSS JOIN loads
GROUP BY l.alert_id
HAVING LOGICAL_OR(l.is_rail_route)
