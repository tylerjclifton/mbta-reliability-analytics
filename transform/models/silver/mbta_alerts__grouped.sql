{#
  silver.mbta_alerts__grouped — one row per service-affecting alert × route, with its incident

  Logic step 2 of 2 for alerts (step 1: silver.mbta_alerts__resolved). Groups alerts
  into incidents and presents them in project conventions; gold reads this.

  Incidents: the MBTA often posts several alerts for one event — an update, or a
  follow-up such as "delays due to an earlier disabled train at JFK/UMass". An
  alert continues the previous incident when it has the same route, cause,
  effect, and location, and starts within 2 hours of the incident's latest end
  (6 hours when its header says "earlier" or "residual"). Alerts at different
  stations are always separate incidents. incident_id is the first alert's ID.

  Steps:
    1. located         — pull the station/area out of the header ("at Harvard")
    2. incident_breaks — flag alerts that start a new incident (see above)
    3. incidents       — number incidents and assign incident_id
    4. final select    — human-readable enums, derive dates and duration
#}

WITH

    -- 1. Location named after at/near/between/from: the run of capitalized words
    --    ("JFK/UMass", "Revere Beach and Beachmont"), lower-cased with
    --    punctuation stripped so "at JFK/UMass" and "near JFK/UMass" match.
    --    NULL when the header names no location.
    located AS (
        SELECT
            *,
            REGEXP_REPLACE(
                -- A regex can't be wrapped, so this line is exempt from the length rule
                LOWER(REGEXP_EXTRACT(alert_header, r"(?:\bat|\bnear|\bbetween|\bfrom) ((?:[A-Z][\w/'-]*)(?: (?:[A-Z][\w/'-]*|and))*)")),  -- noqa: LT05
                r'[^a-z]', ''
            ) AS location_key,
            REGEXP_CONTAINS(LOWER(alert_header), r'\b(earlier|residual)\b') AS is_follow_up_wording
        FROM {{ ref('mbta_alerts__resolved') }}
    ),

    -- 2. Within each route × cause × effect × location group (alerts with no
    --    location never group), an alert starts a new incident unless it
    --    begins within the follow-up window of the latest end seen so far
    incident_breaks AS (
        SELECT
            *,
            IF(
                group_latest_end_at IS NOT NULL
                AND alert_start_at <= TIMESTAMP_ADD(group_latest_end_at, INTERVAL IF(is_follow_up_wording, 6, 2) HOUR),
                0, 1
            ) AS is_new_incident
        FROM (
            SELECT
                *,
                -- Latest end among the group's earlier alerts (ongoing = now)
                MAX(COALESCE(alert_end_at, CURRENT_TIMESTAMP())) OVER (
                    PARTITION BY route_id, alert_cause, alert_effect, COALESCE(location_key, alert_id)
                    ORDER BY alert_start_at, alert_id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS group_latest_end_at
            FROM located
        ) AS with_group_end
    ),

    -- 3. A running count of new-incident flags numbers the incidents in each
    --    group; the incident's first alert ID becomes its incident_id
    incidents AS (
        SELECT
            *,
            FIRST_VALUE(alert_id) OVER (
                PARTITION BY route_id, alert_cause, alert_effect, COALESCE(location_key, alert_id), incident_number
                ORDER BY alert_start_at, alert_id
            ) AS incident_id
        FROM (
            SELECT
                *,
                SUM(is_new_incident) OVER (
                    PARTITION BY route_id, alert_cause, alert_effect, COALESCE(location_key, alert_id)
                    ORDER BY alert_start_at, alert_id
                ) AS incident_number
            FROM incident_breaks
        ) AS with_incident_number
    )

-- 4. Project conventions: `_at` timestamps (UTC), `_date` dates (Eastern),
--    human-readable enums
SELECT
    alert_id,
    route_id,
    incident_id,
    alert_header,
    alert_description,
    INITCAP(REPLACE(alert_cause, '_', ' '))                     AS alert_cause,
    INITCAP(REPLACE(alert_effect, '_', ' '))                    AS alert_effect,
    alert_severity,
    INITCAP(REPLACE(alert_duration_certainty, '_', ' '))        AS alert_duration_certainty,
    alert_start_at,
    alert_end_at,
    DATE(alert_start_at, '{{ var("local_timezone") }}')         AS alert_start_date,
    DATE(alert_end_at, '{{ var("local_timezone") }}')           AS alert_end_date,
    -- Ongoing alerts are measured up to now
    TIMESTAMP_DIFF(COALESCE(alert_end_at, CURRENT_TIMESTAMP()), alert_start_at, MINUTE) AS alert_duration_minutes,
    location_key                                                AS alert_location_key,
    alert_created_at,
    alert_updated_at,
    is_in_feed,
    first_seen_at,
    last_seen_at,
    -- The latest version of an alert is the one from its last-seen run
    last_seen_at                                                AS ingested_at,
    'ingest-mbta-alerts'                                        AS ingested_by
FROM incidents
