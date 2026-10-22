{#
  gold.rail_ridership — one row per service date × line

  Daily ridership with the number of incidents active on that line that day
  and that day's weather at Boston Logan, for the dashboard's ridership views.

  Two incident counts: all incidents, and disruptions — incidents lasting under
  24 hours (a delay, a disabled train). Long planned closures (a station shut
  for months) are active every day, so they'd make every day an "incident day";
  the disruption count leaves them out.

  Steps:
    1. incident_counts — count distinct incidents (and disruptions) active per
                         service date × line
    2. final select    — ridership + incident count + weather
#}

WITH

    -- 1. An incident counts toward every service date between its start and
    --    end (or today, if ongoing). Incidents are per route; COUNT(DISTINCT)
    --    counts one that spans several Green Line branches once for the line.
    incident_counts AS (
        SELECT
            d.service_date,
            d.line_name,
            COUNT(DISTINCT i.incident_id) AS active_incident_count,
            COUNT(DISTINCT IF(i.incident_duration_minutes < 24 * 60, i.incident_id, NULL)) AS active_disruption_count
        FROM {{ ref('mbta_ridership') }} AS d
        LEFT JOIN {{ ref('rail_incidents') }} AS i
            ON  d.line_name = i.line_name
            AND d.service_date BETWEEN i.incident_start_date
                AND COALESCE(i.incident_end_date, CURRENT_DATE('{{ var("local_timezone") }}'))
        GROUP BY
            d.service_date,
            d.line_name
    )

-- 2. Ridership with incident counts and weather. Weather is LEFT joined so a day
--    without weather still shows ridership (the not_null warning flags it).
SELECT
    d.service_date,
    d.line_name,
    d.gated_entries,
    ic.active_incident_count,
    ic.active_disruption_count,
    w.avg_temperature_f,
    w.max_temperature_f,
    w.min_temperature_f,
    w.precipitation_in,
    w.snowfall_in,
    d.ingested_at               AS ridership_ingested_at,
    w.ingested_at               AS weather_ingested_at
FROM {{ ref('mbta_ridership') }} AS d
INNER JOIN incident_counts AS ic
    ON  d.service_date = ic.service_date
    AND d.line_name = ic.line_name
LEFT JOIN {{ ref('noaa_weather') }} AS w
    ON d.service_date = w.observation_date
