{#
  silver.mbta_ferry_trips__base — one row per ferry trip leg

  Every ferry trip leg as of its latest pull, typed: the actual times parsed
  from Eastern local text, rider counts as numbers (riders off made positive),
  and the MBTA's "NA" as NULL (decision 0018).

  Each weekly run re-pulls the last year of service, so bronze holds a service
  day's legs once per run that covered it, and the latest run's set stands.
  Whole days are replaced, not legs matched one by one: older years have no
  trip or leg IDs to match on.

  Incremental, like silver.lamp_alerts__base (decision 0010): a view would
  re-read every weekly re-pull of the year, ~2.8 million rows a year more,
  each time it's read. Each run reads only loads added since the last and
  overwrites the service days they cover; `dbt build --full-refresh` rebuilds
  it from bronze.

  Steps:
    1. new_loads    — bronze rows from loads not yet processed (all of
                      bronze on a first build)
    2. latest       — each service day's legs from the latest of those loads
    3. final select — typed, in project conventions
#}

{{
    config(
        materialized='incremental',
        incremental_strategy='insert_overwrite',
        partition_by={'field': 'service_date', 'data_type': 'date', 'granularity': 'day'},
        cluster_by=['route_id'],
        on_schema_change='append_new_columns'
    )
}}

{#- The newest load already processed (none on a first build). -#}
{%- set processed_through = last_processed_snapshot('ingested_at') %}

WITH

    -- 1. Loads not yet processed.
    new_loads AS (
        SELECT *
        FROM {{ source('bronze', 'mbta_ferry_trips') }}
        {%- if processed_through %}
        WHERE ingested_at > TIMESTAMP '{{ processed_through }}'
        {%- endif %}
    ),

    -- 2. Each service day's legs from the latest load that covered it.
    latest AS (
        SELECT *
        FROM new_loads
        QUALIFY ingested_at = MAX(ingested_at) OVER (PARTITION BY service_date)
    )

-- 3. Typed. A route's name is its ID and place ("F4-Charlestown").
SELECT
    service_date,
    route_id,
    route_name,
    sub_route,
    NULLIF(trip_id, 'NA')                           AS trip_id,
    NULLIF(stop_id, 'NA')                           AS leg_id,
    departure_terminal,
    arrival_terminal,
    NULLIF(travel_direction, 'NA')                  AS travel_direction,
    NULLIF(trip_endpoint, 'NA')                     AS trip_endpoint,
    mbta_sched_departure                            AS scheduled_departure_at,
    {{ eastern_time_from_text('actual_departure') }} AS actual_departure_at,
    mbta_sched_arrival                              AS scheduled_arrival_at,
    {{ eastern_time_from_text('actual_arrival') }}   AS actual_arrival_at,
    SAFE_CAST(pax_on AS INT64)                      AS riders_on,
    SAFE_CAST(pax_load AS INT64)                    AS riders_aboard,
    ABS(SAFE_CAST(pax_off AS INT64))                AS riders_off,
    ingested_at,
    ingested_by
FROM latest
