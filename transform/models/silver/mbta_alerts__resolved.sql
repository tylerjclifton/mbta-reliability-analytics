{#
  silver.mbta_alerts__resolved — one row per service-affecting alert × route

  Logic step 1 of 2 for alerts (step 2: silver.mbta_alerts__grouped). Keeps the
  alerts that affect train service, and works out when each one really started
  and ended, and whether it's still in the live feed.

    start  = posted start, else when MBTA created the alert
    end    = whichever comes first:
               - the end time the MBTA posted (an estimate, usually on the hour)
               - when the alert left the feed: halfway between the last ingest
                 run that saw it and the next run (runs are every 15 minutes),
                 capped at 30 minutes after it was last seen
             NULL while the alert is still in the feed with no posted end
  Announced alerts that left the feed before their start never took effect
  (cancelled, or re-posted under a new alert ID) and are dropped.

  Steps:
    1. runs     — every ingest run and the run after it
    2. cleaned  — drop non-service effects; flag alerts still in the feed;
                  when each alert left the feed
    3. resolved — start/end per the rules above; drop alerts that left the
                  feed before they started
#}

WITH

    -- 1. Ingest runs, to the minute (rows from one run share a timestamp; rows
    --    from the pre-2026-10 pipeline differ by microseconds within a run),
    --    from both alert tables: the frozen shaped one and raw. Runs where both
    --    were written collapse into one. Reads only the ingested_at columns,
    --    so it stays cheap.
    runs AS (
        SELECT
            run_at,
            LEAD(run_at) OVER (ORDER BY run_at) AS next_run_at,
            MAX(run_at) OVER ()                 AS latest_run_at
        FROM (
            SELECT TIMESTAMP_TRUNC(ingested_at, MINUTE) AS run_at
            FROM {{ source('bronze', 'mbta_alerts_legacy') }}
            UNION DISTINCT
            SELECT TIMESTAMP_TRUNC(ingested_at, MINUTE) AS run_at
            FROM {{ source('bronze', 'mbta_alerts') }}
        )
    ),

    -- 2. Keep service-affecting alerts (judged on the latest version's effect).
    --    An alert seen in the latest run is still in the live feed.
    cleaned AS (
        SELECT
            a.*,
            r.run_at = r.latest_run_at AS is_in_feed,
            -- It left the feed between its last run and the next; take the
            -- midpoint, capped at 30 minutes. Runs were never scheduled more than
            -- an hour apart, but history carried over from the pre-2026-10
            -- pipeline only kept each alert's last sighting, so its run list has
            -- gaps that would otherwise push the midpoint hours too late.
            TIMESTAMP_ADD(
                a.last_seen_at,
                INTERVAL LEAST(DIV(TIMESTAMP_DIFF(r.next_run_at, r.run_at, SECOND), 2), 30 * 60) SECOND
            )                          AS left_feed_at
        FROM {{ ref('mbta_alerts__by_route') }} AS a
        INNER JOIN runs AS r
            ON TIMESTAMP_TRUNC(a.last_seen_at, MINUTE) = r.run_at
        -- Exempt from the length rule: the line is only long once the effect list is rendered
        WHERE a.alert_effect NOT IN ('{{ var("non_service_alert_effects") | join("', '") }}')  -- noqa: LT05
    )

-- 3. Resolve start and end
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
    -- No posted start → fall back to when the alert was created
    COALESCE(posted_start_at, alert_created_at) AS alert_start_at,
    CASE
        -- Still in the feed → ends at its posted end (NULL = ongoing)
        WHEN is_in_feed THEN posted_end_at
        -- Left the feed → whichever came first: the posted end or leaving
        WHEN posted_end_at < left_feed_at THEN posted_end_at
        ELSE left_feed_at
    END                                         AS alert_end_at
FROM cleaned
-- Left the feed before starting → never took effect
WHERE is_in_feed OR left_feed_at > COALESCE(posted_start_at, alert_created_at)
