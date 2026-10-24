{#
  gold.rail_incident_stations — one row per incident × route × station

  The stations each incident affects, with coordinates and the incident's
  details, for the dashboard's map: what's affected right now, and which
  stations get hit most. Built from the stops each alert names
  (silver.mbta_alert_stops), so it covers incidents since raw alert capture
  began on 2026-10-24, and only alerts that name stations — most delays are
  line-wide and have no rows.

  Steps:
    1. alert_stations    — each service alert's stations, tagged with its incident
    2. incident_stations — collapsed to incident × route × station; both
                           directions if any alert affects both, or alerts differ
    3. stations          — each station's name and coordinates
    4. final select      — with the incident's details, the station's location,
                           and which way the affected direction runs
#}

WITH

    -- 1. Stations per service-affecting alert (silver.mbta_alerts drops the rest)
    alert_stations AS (
        SELECT
            a.incident_id,
            s.route_id,
            s.station_id,
            s.affects_both_directions,
            s.direction_id
        FROM {{ ref('mbta_alerts') }} AS a
        INNER JOIN {{ ref('mbta_alert_stops') }} AS s
            ON
                a.alert_id = s.alert_id
                AND a.route_id = s.route_id
    ),

    -- 2. One row per incident × route × station
    incident_stations AS (
        SELECT
            incident_id,
            route_id,
            station_id,
            LOGICAL_OR(affects_both_directions) OR COUNT(DISTINCT direction_id) > 1 AS affects_both_directions,
            IF(
                LOGICAL_OR(affects_both_directions) OR COUNT(DISTINCT direction_id) > 1,
                NULL,
                ANY_VALUE(direction_id)
            )                                                                       AS direction_id
        FROM alert_stations
        GROUP BY
            incident_id,
            route_id,
            station_id
    ),

    -- 3. Station name and coordinates (the station's own row, any route)
    stations AS (
        SELECT
            station_id,
            ANY_VALUE(station_name)   AS station_name,
            ANY_VALUE(stop_latitude)  AS station_latitude,
            ANY_VALUE(stop_longitude) AS station_longitude
        FROM {{ ref('mbta_stops') }}
        WHERE stop_type = 'Station'
        GROUP BY station_id
    )

-- 4. Incident details, station location, and the affected direction's terminal
--    (route_destinations is "['Ashmont/Braintree', 'Alewife']", indexed by
--    direction_id)
SELECT
    st.incident_id,
    st.route_id,
    st.station_id,
    i.route_name,
    i.line_name,
    s.station_name,
    s.station_latitude,
    s.station_longitude,
    st.affects_both_directions,
    REGEXP_EXTRACT_ALL(r.route_destinations, r"'([^']*)'")[SAFE_OFFSET(st.direction_id)] AS direction_destination,
    i.incident_cause,
    i.incident_effect,
    i.incident_header,
    i.incident_start_at,
    i.incident_end_at,
    i.is_in_feed,
    i.ingested_at
FROM incident_stations AS st
INNER JOIN {{ ref('rail_incidents') }} AS i
    ON
        st.incident_id = i.incident_id
        AND st.route_id = i.route_id
LEFT JOIN stations AS s
    ON st.station_id = s.station_id
LEFT JOIN {{ ref('mbta_routes') }} AS r
    ON st.route_id = r.route_id
