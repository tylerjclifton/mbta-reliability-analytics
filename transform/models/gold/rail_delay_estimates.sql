{#
  gold.rail_delay_estimates — one row per subway delay alert × line

  The end the MBTA first posted for each delay, against when it actually
  cleared, for the dashboard's estimates card. From the LAMP archive, which
  keeps every version of every alert (silver.lamp_alerts__base); it's topped
  up weekly, so the newest week's delays arrive with the next load.

  Steps:
    1. delay_lines  — closed delay alerts with a first posted end, one row per
                      line they name
    2. final select — minutes from posting to the estimated end and to the
                      all-clear
#}

WITH

    -- 1. Closed delays with a first estimate, once per line they name.
    delay_lines AS (
        SELECT DISTINCT
            a.alert_id,
            r.line_name,
            a.alert_cause,
            a.alert_created_at,
            a.first_posted_end_at,
            a.alert_closed_at
        FROM {{ ref('lamp_alerts__base') }} AS a
        CROSS JOIN UNNEST(a.informed_entities) AS entity
        INNER JOIN {{ ref('mbta_routes__base') }} AS r
            ON entity.route_id = r.route_id
        WHERE
            a.alert_effect = 'DELAY'
            AND a.first_posted_end_at IS NOT NULL
            AND a.alert_closed_at >= a.alert_created_at
    )

-- 2. Minutes to the first estimate and to the all-clear.
SELECT
    alert_id,
    line_name,
    alert_cause,
    alert_created_at,
    first_posted_end_at,
    alert_closed_at,
    TIMESTAMP_DIFF(first_posted_end_at, alert_created_at, SECOND) / 60 AS estimated_minutes,
    TIMESTAMP_DIFF(alert_closed_at, alert_created_at, SECOND) / 60     AS actual_minutes
FROM delay_lines
