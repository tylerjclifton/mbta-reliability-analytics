{#
  silver.mbta_alerts__by_period — one row per alert × route × active period

  When each alert's service effect was actually in force. Most alerts post one
  active period, but planned work can post several (each weekend of a month,
  or every night for a year), and silver.mbta_alerts__resolved keeps only the
  first as the alert's start and end, so an incident is counted and timed
  once. A reshaping step beside the alert × route models, as
  silver.mbta_alerts__by_station is: it changes nothing about them.

  Each posted period ends at the earlier of its own end and when the alert
  stopped: the MBTA closed it, or (for snapshots) it left the feed. Periods
  that would start after the alert stopped never happened and are left out.
  An alert that posted no period is one period, its start to its end in
  silver.mbta_alerts__resolved. The first period is always that row's start
  and end, by the same rules.

  Steps:
    1. stops        — per alert × route: when it stopped, NULL while it's
                      still in force
    2. periods      — each posted period (or the resolved span when there's
                      none), cut off where the alert stopped
    3. final select — one row per period start
#}

WITH

    -- 1. When each alert stopped: its close, or when it left the feed. An
    --    alert still in the feed and not closed hasn't stopped.
    stops AS (
        SELECT
            *,
            COALESCE(alert_closed_at, IF(is_in_feed, NULL, left_feed_at)) AS stopped_at
        FROM {{ ref('mbta_alerts__resolved') }}
    ),

    -- 2. Each period that took effect, cut off where the alert stopped. A
    --    posted period with no end runs until then (NULL while ongoing).
    periods AS (
        SELECT
            s.alert_id,
            s.route_id,
            p.start_at,
            CASE
                WHEN p.end_at IS NULL THEN s.stopped_at
                WHEN s.stopped_at IS NULL THEN p.end_at
                ELSE LEAST(p.end_at, s.stopped_at)
            END AS end_at
        FROM stops AS s
        CROSS JOIN UNNEST(
            IF(
                ARRAY_LENGTH(s.active_periods) > 0,
                s.active_periods,
                [STRUCT(s.alert_start_at AS start_at, s.alert_end_at AS end_at)]
            )
        ) AS p
        WHERE s.stopped_at IS NULL OR p.start_at < s.stopped_at
    )

-- 3. One row per start: the rare alert that posts two periods starting
--    together (a few, with different ends) keeps the longer, an open end
--    being longest.
SELECT
    alert_id,
    route_id,
    start_at                                             AS period_start_at,
    IF(LOGICAL_OR(end_at IS NULL), NULL, MAX(end_at))    AS period_end_at
FROM periods
GROUP BY
    alert_id,
    route_id,
    start_at
