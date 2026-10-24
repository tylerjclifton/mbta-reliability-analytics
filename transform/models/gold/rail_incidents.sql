{#
  gold.rail_incidents — one row per incident × route

  An incident is one real-world event (a disabled train, a signal problem, a
  planned shutdown) that the MBTA may have posted as several alerts; grouping
  rules live in silver.alert_incidents. The dashboard counts, times, and
  categorizes incidents so a re-posted event isn't counted twice.

  stations_affected counts the stations the incident's alerts name. It needs
  the alerts' raw JSON, captured since 2026-10-24: NULL means none of the
  incident's alerts were captured (so unknown), while 0 means they were but
  named no stations, as with most line-wide delays.

  Steps:
    1. incident_alerts   — every alert with its route's name, line, and type
    2. incident_stations — per incident × route: whether any alert has raw
                           data, and how many distinct stations they name
    3. incidents         — one row per incident: the span of all its alerts,
                           the latest alert's text, and how many alerts it took
    4. final select      — incidents with their station count
#}

WITH

    -- 1. Alerts with route metadata
    incident_alerts AS (
        SELECT
            a.*,
            r.route_name,
            r.line_name,
            r.route_type
        FROM {{ ref('alert_incidents') }} AS a
        LEFT JOIN {{ ref('mbta_routes') }} AS r
            ON a.route_id = r.route_id
    ),

    -- 2. Stations named across each incident's alerts
    incident_stations AS (
        SELECT
            a.incident_id,
            a.route_id,
            LOGICAL_OR(raw.alert_id IS NOT NULL) AS has_stop_data,
            COUNT(DISTINCT s.station_id)         AS station_count
        FROM {{ ref('alert_incidents') }} AS a
        LEFT JOIN {{ ref('mbta_alerts_raw') }} AS raw
            ON a.alert_id = raw.alert_id
        LEFT JOIN {{ ref('alert_stations') }} AS s
            ON
                a.alert_id = s.alert_id
                AND a.route_id = s.route_id
        GROUP BY
            a.incident_id,
            a.route_id
    ),

    -- 3. Collapse each incident's alerts. Start is the earliest alert's start;
    --    end is the latest alert's end, or NULL while any of its alerts is
    --    ongoing. Text comes from the most recent alert, which describes the
    --    latest status.
    incidents AS (
        SELECT
            incident_id,
            route_id,
            ANY_VALUE(route_name)                                       AS route_name,
            ANY_VALUE(line_name)                                        AS line_name,
            ANY_VALUE(route_type)                                       AS route_type,
            -- Identical across the incident's alerts by construction
            ANY_VALUE(alert_cause)                                      AS incident_cause,
            ANY_VALUE(alert_effect)                                     AS incident_effect,
            ARRAY_AGG(
                alert_header ORDER BY alert_start_at DESC, alert_id DESC LIMIT 1
            )[OFFSET(0)]                                                AS incident_header,
            ARRAY_AGG(
                alert_description ORDER BY alert_start_at DESC, alert_id DESC LIMIT 1
            )[OFFSET(0)]                                                AS incident_description,
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
    )

-- 4. Station count: NULL when no alert was captured raw (unknown), else the count
SELECT
    i.* EXCEPT (ingested_at),
    IF(st.has_stop_data, st.station_count, NULL) AS stations_affected,
    i.ingested_at
FROM incidents AS i
LEFT JOIN incident_stations AS st
    ON
        i.incident_id = st.incident_id
        AND i.route_id = st.route_id
