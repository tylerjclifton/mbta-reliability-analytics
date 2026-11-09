{#
  silver.mbta_alerts__resolved — one row per service-affecting alert × route

  Logic step 1 of 2 for alerts (step 2: silver.mbta_alerts__grouped). Keeps the
  alerts that affect train service, and works out when each one really started
  and ended, and whether it's still in the live feed.

  Two sources, split at full-JSON capture (var alerts_raw_capture_start;
  decision 0016):
    - alerts seen since then: the project's own 15-minute snapshots
      (silver.mbta_alerts__by_route)
    - alerts that ended before then: the MBTA's LAMP archive
      (silver.lamp_alerts__by_route), from var lamp_alerts_start on

    start  = posted start, else when MBTA created the alert
    end    = whichever comes first:
               - the end time the MBTA posted (an estimate, usually on the hour)
               - when the MBTA closed it: always known for LAMP alerts, and for
                 snapshot alerts when a run caught it closed (alerts stay in
                 the feed a few minutes after closing)
               - otherwise, for snapshots, when the alert left the feed:
                 halfway between the last ingest run that saw it and the next
                 run (runs are every 15 minutes), capped at 30 minutes after it
                 was last seen
             NULL while the alert is still in the feed, open, with no posted end
  Alerts that ended before their start never took effect (canceled, or
  re-posted under a new alert ID) and are dropped, as are LAMP alerts with
  neither a close nor a posted end.

  Steps:
    1. runs     — every ingest run the snapshots table has processed, and the
                  run after it
    2. cleaned  — snapshots: drop non-service effects; flag alerts still in the
                  feed; when each alert left the feed
    3. lamp     — LAMP: service-affecting alerts the snapshots never saw, with
                  their end; only those that ended before the capture start
    4. resolved — start/end per the rules above, both sources; drop alerts
                  that ended before they started

  Unit tests for these rules: _silver__unit_tests.yml (resolved_*).
#}

{%- set capture_start = "TIMESTAMP '" ~ var('alerts_raw_capture_start') ~ "'" -%}
{%- set non_service_effects = "('" ~ var('non_service_alert_effects') | join("', '") ~ "')" %}

WITH

    -- 1. Ingest runs, to the minute (rows from one run share a timestamp), up
    --    to the newest one silver.mbta_alerts__by_route has processed: every
    --    run holds rail alerts, so that's its newest last_seen_at. A run that
    --    lands mid-transform isn't in that table yet, and judging against it
    --    would make every alert look gone from the feed. Reads only one
    --    column of each, so it stays cheap.
    runs AS (
        SELECT
            run_at,
            LEAD(run_at) OVER (ORDER BY run_at) AS next_run_at,
            MAX(run_at) OVER ()                 AS latest_run_at
        FROM (
            SELECT DISTINCT TIMESTAMP_TRUNC(ingested_at, MINUTE) AS run_at
            FROM {{ source('bronze', 'mbta_alerts') }}
            WHERE ingested_at <= (
                SELECT MAX(processed.last_seen_at) FROM {{ ref('mbta_alerts__by_route') }} AS processed
            )
        )
    ),

    -- 2. Service-affecting snapshot alerts (judged on the latest version's
    --    effect). An alert seen in the latest run is still in the live feed.
    cleaned AS (
        SELECT
            a.*,
            r.run_at = r.latest_run_at AS is_in_feed,
            -- It left the feed between its last run and the next; take the
            -- midpoint, capped at 30 minutes so a gap in the runs (a pipeline
            -- outage) can't push it hours too late.
            TIMESTAMP_ADD(
                a.last_seen_at,
                INTERVAL LEAST(DIV(TIMESTAMP_DIFF(r.next_run_at, r.run_at, SECOND), 2), 30 * 60) SECOND
            )                          AS left_feed_at
        FROM {{ ref('mbta_alerts__by_route') }} AS a
        INNER JOIN runs AS r
            ON TIMESTAMP_TRUNC(a.last_seen_at, MINUTE) = r.run_at
        WHERE
            -- Exempt from the length rule: the line is only long once
            -- the effect list is rendered.
            a.alert_effect NOT IN {{ non_service_effects }}  -- noqa: LT05
            -- Rows last seen before full-JSON capture are history from the
            -- frozen table, which LAMP replaces.
            AND a.last_seen_at >= {{ capture_start }}
    ),

    -- 3. LAMP alerts the snapshots never saw, ending at whichever came first:
    --    the posted end or the close. Kept only if that's before the capture
    --    start; later ones are the snapshots' to record (decision 0016).
    lamp AS (
        SELECT
            *,
            CASE
                WHEN posted_end_at < alert_closed_at THEN posted_end_at
                ELSE COALESCE(alert_closed_at, posted_end_at)
            END AS lamp_end_at
        FROM {{ ref('lamp_alerts__by_route') }}
        WHERE
            alert_effect NOT IN {{ non_service_effects }}  -- noqa: LT05
            AND alert_created_at >= TIMESTAMP('{{ var("lamp_alerts_start") }}', '{{ var("local_timezone") }}')
            AND alert_id NOT IN (
                SELECT seen.alert_id
                FROM {{ ref('mbta_alerts__by_route') }} AS seen
                WHERE seen.last_seen_at >= {{ capture_start }}
            )
    )

-- 4. Resolve start and end.
SELECT
    alert_id,
    route_id,
    posted_start_at,
    posted_end_at,
    alert_duration_certainty,
    alert_header,
    alert_description,
    alert_cause,
    alert_effect,
    alert_severity,
    alert_created_at,
    alert_updated_at,
    first_seen_at,
    last_seen_at,
    is_in_feed,
    left_feed_at,
    alert_closed_at,
    -- No posted start → fall back to when the alert was created.
    COALESCE(posted_start_at, alert_created_at) AS alert_start_at,
    CASE
        -- Caught closed → whichever came first: the posted end or the close.
        WHEN posted_end_at < alert_closed_at THEN posted_end_at
        WHEN alert_closed_at IS NOT NULL THEN alert_closed_at
        -- Still in the feed → ends at its posted end (NULL = ongoing).
        WHEN is_in_feed THEN posted_end_at
        -- Left the feed → whichever came first: the posted end or leaving.
        WHEN posted_end_at < left_feed_at THEN posted_end_at
        ELSE left_feed_at
    END                                         AS alert_end_at,
    -- The latest version is the one from the alert's last-seen run.
    last_seen_at                                AS ingested_at,
    'ingest-mbta-alerts'                        AS ingested_by
FROM cleaned
-- Left the feed or closed before starting → never took effect.
WHERE
    (is_in_feed OR left_feed_at > COALESCE(posted_start_at, alert_created_at))
    AND (alert_closed_at IS NULL OR alert_closed_at > COALESCE(posted_start_at, alert_created_at))

UNION ALL

SELECT
    alert_id,
    route_id,
    posted_start_at,
    posted_end_at,
    alert_duration_certainty,
    alert_header,
    alert_description,
    alert_cause,
    alert_effect,
    alert_severity,
    alert_created_at,
    alert_updated_at,
    CAST(NULL AS TIMESTAMP)                     AS first_seen_at,
    CAST(NULL AS TIMESTAMP)                     AS last_seen_at,
    FALSE                                       AS is_in_feed,
    CAST(NULL AS TIMESTAMP)                     AS left_feed_at,
    alert_closed_at,
    COALESCE(posted_start_at, alert_created_at) AS alert_start_at,
    lamp_end_at                                 AS alert_end_at,
    ingested_at,
    ingested_by
FROM lamp
WHERE
    lamp_end_at < {{ capture_start }}
    -- Ended before starting → never took effect.
    AND lamp_end_at > COALESCE(posted_start_at, alert_created_at)
