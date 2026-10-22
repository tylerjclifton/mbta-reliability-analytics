{#
  silver.mbta_alerts — one row per service-affecting alert × route

  Takes the latest version of each alert (silver.mbta_alert_latest), drops
  alerts that don't affect train service (var non_service_alert_effects, e.g.
  notices and elevator closures), resolves when each alert started and ended,
  and groups alerts into incidents.

    start  = API start, else when MBTA created the alert
    end    = whichever comes first:
               - the end time the MBTA posted (an estimate, usually on the hour)
               - when the alert left the feed: halfway between the last ingest
                 run that saw it and the next run (runs are every 15 minutes),
                 capped at 30 minutes after it was last seen
             NULL while the alert is still in the feed with no posted end

  Announced alerts that left the feed before their start never took effect
  (cancelled, or re-posted under a new alert ID) and are dropped.

  Steps:
    1. runs            — every ingest run and the run after it
    2. cleaned         — drop non-service effects; epoch placeholders → NULL;
                         flag alerts still in the feed
    3. resolved        — start/end per the rules above; drop alerts that left
                         the feed before they started
    4. located         — pull the station/area out of the header ("at Harvard")
    5. incident_breaks — flag alerts that start a new incident (see below)
    6. incidents       — number incidents and assign incident_id
    7. final select    — rename to project conventions, derive dates and duration

  Incidents: the MBTA often posts several alerts for one event — an update, or a
  follow-up such as "delays due to an earlier disabled train at JFK/UMass". An
  alert continues the previous incident when it has the same route, cause,
  effect, and location, and starts within 2 hours of the incident's latest end
  (6 hours when its header says "earlier" or "residual"). Alerts at different
  stations are always separate incidents. incident_id is the first alert's ID.
#}

WITH

    -- 1. Ingest runs, to the minute (rows from one run share a timestamp; rows
    --    from the pre-2026-10 pipeline differ by microseconds within a run).
    --    Reads only the ingested_at column of bronze, so it stays cheap.
    runs AS (
        SELECT
            run_at,
            LEAD(run_at) OVER (ORDER BY run_at) AS next_run_at,
            MAX(run_at) OVER ()                 AS latest_run_at
        FROM (
            SELECT DISTINCT TIMESTAMP_TRUNC(ingested_at, MINUTE) AS run_at
            FROM {{ source('bronze', 'mbta_alerts') }}
        )
    ),

    -- 2. Keep service-affecting alerts (judged on the latest version's effect).
    --    The API uses the epoch (1970-01-01) for "not set"; treat it as NULL.
    --    An alert seen in the latest run is still in the live feed.
    cleaned AS (
        SELECT
            a.*,
            IF(a.active_period_start > TIMESTAMP '1970-01-02', a.active_period_start, NULL) AS api_start_at,
            IF(a.active_period_end   > TIMESTAMP '1970-01-02', a.active_period_end,   NULL) AS api_end_at,
            r.run_at = r.latest_run_at                                                    AS is_in_feed,
            -- It left the feed between its last run and the next; take the
            -- midpoint, capped at 30 minutes. Runs were never scheduled more than
            -- an hour apart, but history carried over from the pre-2026-10
            -- pipeline only kept each alert's last sighting, so its run list has
            -- gaps that would otherwise push the midpoint hours too late.
            TIMESTAMP_ADD(
                a.last_seen_at,
                INTERVAL LEAST(DIV(TIMESTAMP_DIFF(r.next_run_at, r.run_at, SECOND), 2), 30 * 60) SECOND
            )                                                                             AS left_feed_at
        FROM {{ ref('mbta_alert_latest') }} AS a
        INNER JOIN runs AS r
            ON TIMESTAMP_TRUNC(a.last_seen_at, MINUTE) = r.run_at
        -- Exempt from the length rule: the line is only long once the effect list is rendered
        WHERE a.effect NOT IN ('{{ var("non_service_alert_effects") | join("', '") }}')  -- noqa: LT05
    ),

    -- 3. Resolve start and end
    resolved AS (
        SELECT
            *,
            -- No real start from the API → fall back to when the alert was created
            COALESCE(api_start_at, created_at) AS start_at,
            CASE
                -- Still in the feed → ends at its posted end (NULL = ongoing)
                WHEN is_in_feed THEN api_end_at
                -- Left the feed → whichever came first: the posted end or leaving
                WHEN api_end_at < left_feed_at THEN api_end_at
                ELSE left_feed_at
            END AS end_at
        FROM cleaned
        -- Left the feed before starting → never took effect
        WHERE is_in_feed OR left_feed_at > COALESCE(api_start_at, created_at)
    ),

    -- 4. Location named after at/near/between/from: the run of capitalized words
    --    ("JFK/UMass", "Revere Beach and Beachmont"), lower-cased with
    --    punctuation stripped so "at JFK/UMass" and "near JFK/UMass" match.
    --    NULL when the header names no location.
    located AS (
        SELECT
            *,
            REGEXP_REPLACE(
                -- A regex can't be wrapped, so this line is exempt from the length rule
                LOWER(REGEXP_EXTRACT(header, r"(?:\bat|\bnear|\bbetween|\bfrom) ((?:[A-Z][\w/'-]*)(?: (?:[A-Z][\w/'-]*|and))*)")),  -- noqa: LT05
                r'[^a-z]', ''
            ) AS location_key,
            REGEXP_CONTAINS(LOWER(header), r'\b(earlier|residual)\b') AS is_follow_up_wording
        FROM resolved
    ),

    -- 5. Within each route × cause × effect × location group (alerts with no
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

    -- 6. A running count of new-incident flags numbers the incidents in each
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

-- 7. Project conventions: alert_* attributes, `_at` timestamps (UTC),
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
    -- The latest version of an alert is the one from its last-seen run
    last_seen_at                                                AS ingested_at,
    'ingest-mbta-alerts'                                        AS ingested_by
FROM incidents
