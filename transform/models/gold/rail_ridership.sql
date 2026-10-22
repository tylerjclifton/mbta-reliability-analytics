{#
  gold.rail_ridership — one row per service date × line

  Daily ridership with the number of alerts active on that line that day and
  that day's weather at Boston Logan, for the dashboard's ridership views.

  Steps:
    1. line_alerts   — map each alert from route to line (Green-B … → Green Line)
    2. alert_counts  — count distinct alerts active per service date × line
    3. final select  — ridership + alert count + weather
#}

WITH

    -- 1. Alerts are per route, ridership per line. DISTINCT so an alert on
    --    several Green Line branches counts once for the Green Line.
    line_alerts AS (
        SELECT DISTINCT
            r.line_name,
            a.alert_id,
            a.alert_start_date,
            a.alert_end_date
        FROM {{ ref('mbta_alerts') }} a
        INNER JOIN {{ ref('mbta_routes') }} r
            ON a.route_id = r.route_id
    ),

    -- 2. An alert counts toward every service date between its start and end
    --    (or today, if ongoing)
    alert_counts AS (
        SELECT
            d.service_date,
            d.line_name,
            COUNT(DISTINCT la.alert_id) AS active_alert_count
        FROM {{ ref('mbta_ridership') }} d
        LEFT JOIN line_alerts la
            ON  d.line_name = la.line_name
            AND d.service_date BETWEEN la.alert_start_date
                AND COALESCE(la.alert_end_date, CURRENT_DATE('{{ var("local_timezone") }}'))
        GROUP BY
            d.service_date,
            d.line_name
    )

-- 3. Ridership with alert counts and weather. Weather is LEFT joined so a day
--    without weather still shows ridership (the not_null warning flags it).
SELECT
    d.service_date,
    d.line_name,
    d.gated_entries,
    ac.active_alert_count,
    w.avg_temperature_f,
    w.max_temperature_f,
    w.min_temperature_f,
    w.precipitation_in,
    w.snowfall_in,
    d.ingested_at               AS ridership_ingested_at,
    w.ingested_at               AS weather_ingested_at
FROM {{ ref('mbta_ridership') }} d
INNER JOIN alert_counts ac
    ON  d.service_date = ac.service_date
    AND d.line_name = ac.line_name
LEFT JOIN {{ ref('noaa_weather') }} w
    ON d.service_date = w.observation_date
