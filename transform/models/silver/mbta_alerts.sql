{#
  silver.mbta_alerts — one row per service-affecting alert × route

  Collapses the hourly alert snapshots in bronze to the latest version of each
  alert, drops alerts that don't affect train service (var
  non_service_alert_effects, e.g. notices and elevator closures), resolves
  when each alert started and ended, and groups alerts into incidents. The MBTA API often leaves start
  or end unset (or sets them to the epoch), and drops alerts from the feed when
  they end, so:

    start  = API start, else when MBTA created the alert
    end    = API end, else NULL while the alert is still in the feed,
             else halfway between the last run that saw it and the next (hourly) run

  Steps:
    1. latest_run      — timestamp of the most recent ingest run
    2. latest_versions — latest snapshot per alert × route, plus first/last seen
    3. cleaned         — drop non-service effects; epoch placeholders → NULL;
                         flag alerts still in the feed
    4. resolved        — start/end per the rules above
    5. located         — pull the station/area out of the header ("at Harvard")
    6. incident_breaks — flag alerts that start a new incident (see below)
    7. incidents       — number incidents and assign incident_id
    8. final select    — rename to project conventions, derive dates and duration

  Incidents: the MBTA often posts several alerts for one event — an update, or a
  follow-up such as "delays due to an earlier disabled train at JFK/UMass". An
  alert continues the previous incident when it has the same route, cause,
  effect, and location, and starts within 2 hours of the incident's latest end
  (6 hours when its header says "earlier" or "residual"). Alerts at different
  stations are always separate incidents. incident_id is the first alert's ID.
#}

WITH

    -- 1. Every row written by one ingest run shares its ingested_at, so the
    --    max is the latest run (computed over all effects, before filtering)
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

    -- 3. Keep service-affecting alerts (judged on the latest version's effect).
    --    The API uses the epoch (1970-01-01) for "not set"; treat it as NULL.
    --    An alert seen in the latest run is still in the live feed.
    cleaned AS (
        SELECT
            v.*,
            IF(v.active_period_start > TIMESTAMP '1970-01-02', v.active_period_start, NULL) AS api_start_at,
            IF(v.active_period_end   > TIMESTAMP '1970-01-02', v.active_period_end,   NULL) AS api_end_at,
            v.last_seen_at = r.ingested_at                                                AS is_in_feed
        FROM latest_versions v
        CROSS JOIN latest_run r
        WHERE v.effect NOT IN ('{{ var("non_service_alert_effects") | join("', '") }}')
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
    ),

    -- 5. Location named after at/near/between/from: the run of capitalized words
    --    ("JFK/UMass", "Revere Beach and Beachmont"), lower-cased with
    --    punctuation stripped so "at JFK/UMass" and "near JFK/UMass" match.
    --    NULL when the header names no location.
    located AS (
        SELECT
            *,
            REGEXP_REPLACE(
                LOWER(REGEXP_EXTRACT(header, r"(?:\bat|\bnear|\bbetween|\bfrom) ((?:[A-Z][\w/'-]*)(?: (?:[A-Z][\w/'-]*|and))*)")),
                r'[^a-z]', ''
            ) AS location_key,
            REGEXP_CONTAINS(LOWER(header), r'\b(earlier|residual)\b') AS is_follow_up_wording
        FROM resolved
    ),

    -- 6. Within each route × cause × effect × location group (alerts with no
    --    location never group), an alert starts a new incident unless it
    --    begins within the follow-up window of the latest end seen so far
    incident_breaks AS (
        SELECT
            *,
            IF(
                group_latest_end_at IS NOT NULL
                AND start_at <= TIMESTAMP_ADD(group_latest_end_at, INTERVAL IF(is_follow_up_wording, 6, 2) HOUR),
                0, 1
            ) AS is_new_incident
        FROM (
            SELECT
                *,
                -- Latest end among the group's earlier alerts (ongoing = now)
                MAX(COALESCE(end_at, CURRENT_TIMESTAMP())) OVER (
                    PARTITION BY route, cause, effect, COALESCE(location_key, alert_id)
                    ORDER BY start_at, alert_id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS group_latest_end_at
            FROM located
        )
    ),

    -- 7. A running count of new-incident flags numbers the incidents in each
    --    group; the incident's first alert ID becomes its incident_id
    incidents AS (
        SELECT
            *,
            FIRST_VALUE(alert_id) OVER (
                PARTITION BY route, cause, effect, COALESCE(location_key, alert_id), incident_number
                ORDER BY start_at, alert_id
            ) AS incident_id
        FROM (
            SELECT
                *,
                SUM(is_new_incident) OVER (
                    PARTITION BY route, cause, effect, COALESCE(location_key, alert_id)
                    ORDER BY start_at, alert_id
                ) AS incident_number
            FROM incident_breaks
        )
    )

-- 8. Project conventions: alert_* attributes, `_at` timestamps (UTC),
--    `_date` dates (Eastern), human-readable enums
SELECT
    alert_id,
    route                                                       AS route_id,
    incident_id,
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
    location_key                                                AS alert_location_key,
    created_at                                                  AS alert_created_at,
    updated_at                                                  AS alert_updated_at,
    is_in_feed,
    first_seen_at,
    last_seen_at,
    ingested_at,
    ingested_by
FROM incidents
