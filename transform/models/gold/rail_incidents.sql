{#
  gold.rail_incidents — one row per incident × route

  An incident is one real-world event (a disabled train, a signal problem, a
  planned shutdown) that the MBTA may have posted as several alerts; grouping
  rules live in silver.mbta_alerts. The dashboard counts, times, and
  categorizes incidents so a re-posted event isn't counted twice.

  Steps:
    1. incident_alerts — every alert with its route's name, line, and type
    2. final select    — one row per incident: the span of all its alerts, the
                         latest alert's text, and how many alerts it took
#}

WITH

    -- 1. Alerts with route metadata
    incident_alerts AS (
        SELECT
            a.*,
            r.route_name,
            r.line_name,
            r.route_type
        FROM {{ ref('mbta_alerts') }} AS a
        LEFT JOIN {{ ref('mbta_routes') }} AS r
            ON a.route_id = r.route_id
    )

-- 2. Collapse each incident's alerts. Start is the earliest alert's start; end
--    is the latest alert's end, or NULL while any of its alerts is ongoing.
--    Text comes from the most recent alert, which describes the latest status.
SELECT
    incident_id,
    route_id,
    ANY_VALUE(route_name)                                       AS route_name,
    ANY_VALUE(line_name)                                        AS line_name,
    ANY_VALUE(route_type)                                       AS route_type,
    -- Identical across the incident's alerts by construction
    ANY_VALUE(alert_cause)                                      AS incident_cause,
    ANY_VALUE(alert_effect)                                     AS incident_effect,
    ARRAY_AGG(alert_header ORDER BY alert_start_at DESC, alert_id DESC LIMIT 1)[OFFSET(0)]      AS incident_header,
    ARRAY_AGG(alert_description ORDER BY alert_start_at DESC, alert_id DESC LIMIT 1)[OFFSET(0)] AS incident_description,
    MAX(alert_severity)                                         AS incident_severity,
    MIN(alert_start_at)                                         AS incident_start_at,
    IF(LOGICAL_OR(alert_end_at IS NULL), NULL, MAX(alert_end_at)) AS incident_end_at,
    DATE(MIN(alert_start_at), '{{ var("local_timezone") }}')    AS incident_start_date,
    DATE(
        IF(LOGICAL_OR(alert_end_at IS NULL), NULL, MAX(alert_end_at)),
        '{{ var("local_timezone") }}'
    )                                                           AS incident_end_date,
    -- Ongoing incidents are measured up to now
    TIMESTAMP_DIFF(
        IF(LOGICAL_OR(alert_end_at IS NULL), CURRENT_TIMESTAMP(), MAX(alert_end_at)),
        MIN(alert_start_at),
        MINUTE
    )                                                           AS incident_duration_minutes,
    COUNT(DISTINCT alert_id)                                    AS alert_count,
    LOGICAL_OR(is_in_feed)                                      AS is_in_feed,
    MAX(ingested_at)                                            AS ingested_at
FROM incident_alerts
GROUP BY
    incident_id,
    route_id
