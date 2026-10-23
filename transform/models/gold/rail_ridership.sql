{#
  gold.rail_ridership — one row per service date × line

  Daily ridership with the number of incidents active on that line that day
  and that day's weather at Boston Logan, for the dashboard's ridership views.

  Alongside the incident count, each day gets its most severe service effect
  (shuttle buses, then a suspension, then a delay) and whether it was a calm
  day, so the dashboard can compare ridership by effect against calm days.

  Steps:
    1. incident_counts — count distinct incidents active per service date ×
                         line, the day's most severe effect, and whether it
                         was calm
    2. final select    — ridership + incident count and effect + weather
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
            -- The day's most severe service effect, for comparing ridership by
            -- effect: shuttle buses, then a suspension, then a delay. NULL if
            -- none of those (other effects aren't ranked; see is_calm_day).
            CASE
                WHEN LOGICAL_OR(i.incident_effect = 'Shuttle') THEN 'Shuttle'
                WHEN LOGICAL_OR(i.incident_effect = 'Suspension') THEN 'Suspension'
                WHEN LOGICAL_OR(i.incident_effect = 'Delay') THEN 'Delay'
            END AS most_severe_effect,
            -- Calm: no incident of any kind except station closures, which
            -- close one stop (often for months) rather than disrupt the line.
            -- Any other effect, including ones the MBTA hasn't used yet,
            -- disqualifies the day. Days with no incident count 0 here.
            COUNTIF(i.incident_effect != 'Station Closure') = 0 AS is_calm_day
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
    ic.most_severe_effect,
    ic.is_calm_day,
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
