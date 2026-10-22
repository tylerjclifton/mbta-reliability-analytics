{#
  silver.mbta_alerts — one row per alert × route

  Collapses the hourly alert snapshots in bronze to the latest version of each
  alert and resolves when it started and ended. The MBTA API often leaves start
  or end unset (or sets them to the epoch), and drops alerts from the feed when
  they end, so:

    start  = API start, else when MBTA created the alert
    end    = API end, else NULL while the alert is still in the feed,
             else halfway between the last run that saw it and the next (hourly) run

  Steps:
    1. latest_run      — timestamp of the most recent ingest run
    2. latest_versions — latest snapshot per alert × route, plus first/last seen
    3. cleaned         — epoch placeholders → NULL; flag alerts still in the feed
    4. resolved        — start/end per the rules above
    5. final select    — rename to project conventions, derive dates and duration
#}

WITH

    -- 1. Every row written by one ingest run shares its ingested_at, so the
    --    max is the latest run
    latest_run AS (
        SELECT MAX(ingested_at) AS ingested_at
        FROM {{ source('bronze', 'mbta_alerts') }}
    ),

    -- 2. Latest version of each alert × route, keeping when it was first and
    --    last seen across all snapshots
    latest_versions AS (
        SELECT
            *,
            MIN(ingested_at) OVER alert_snapshots AS first_seen_at,
            MAX(ingested_at) OVER alert_snapshots AS last_seen_at
        FROM {{ source('bronze', 'mbta_alerts') }}
        {{ keep_latest_version(['alert_id', 'route']) }}
        WINDOW alert_snapshots AS (PARTITION BY alert_id, route)
    ),

    -- 3. The API uses the epoch (1970-01-01) for "not set"; treat it as NULL.
    --    An alert seen in the latest run is still in the live feed.
    cleaned AS (
        SELECT
            v.*,
            IF(v.active_period_start > TIMESTAMP '1970-01-02', v.active_period_start, NULL) AS api_start_at,
            IF(v.active_period_end   > TIMESTAMP '1970-01-02', v.active_period_end,   NULL) AS api_end_at,
            v.last_seen_at = r.ingested_at                                                AS is_in_feed
        FROM latest_versions v
        CROSS JOIN latest_run r
    ),

    -- 4. Resolve start and end
    resolved AS (
        SELECT
            *,
            -- No real start from the API → fall back to when the alert was created
            COALESCE(api_start_at, created_at) AS start_at,
            CASE
                -- Explicit end from the API → use it as-is
                WHEN api_end_at IS NOT NULL THEN api_end_at
                -- Still in the feed → genuinely ongoing
                WHEN is_in_feed THEN NULL
                -- Dropped out of the feed with no explicit end → it ended between
                -- the last run that saw it and the next (hourly) one; use the midpoint
                ELSE TIMESTAMP_ADD(last_seen_at, INTERVAL 30 MINUTE)
            END AS end_at
        FROM cleaned
    )

-- 5. Project conventions: alert_* attributes, `_at` timestamps (UTC),
--    `_date` dates (Eastern), human-readable enums
SELECT
    alert_id,
    route                                                       AS route_id,
    header                                                      AS alert_header,
    description                                                 AS alert_description,
    INITCAP(REPLACE(cause, '_', ' '))                           AS alert_cause,
    INITCAP(REPLACE(effect, '_', ' '))                          AS alert_effect,
    severity                                                    AS alert_severity,
    INITCAP(REPLACE(duration_certainty, '_', ' '))              AS alert_duration_certainty,
    start_at                                                    AS alert_start_at,
    end_at                                                      AS alert_end_at,
    DATE(start_at, '{{ var("local_timezone") }}')               AS alert_start_date,
    DATE(end_at, '{{ var("local_timezone") }}')                 AS alert_end_date,
    -- Ongoing alerts are measured up to now
    TIMESTAMP_DIFF(COALESCE(end_at, CURRENT_TIMESTAMP()), start_at, MINUTE) AS alert_duration_minutes,
    created_at                                                  AS alert_created_at,
    updated_at                                                  AS alert_updated_at,
    is_in_feed,
    first_seen_at,
    last_seen_at,
    ingested_at,
    ingested_by
FROM resolved
