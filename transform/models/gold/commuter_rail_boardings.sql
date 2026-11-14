{#
  gold.commuter_rail_boardings — one row per service date × line

  The MBTA's estimated commuter rail boardings per day and line, from
  2020-06-22, for the dashboard's daily commuter rail views. Estimates the
  MBTA doesn't guarantee, months behind (decision 0018).

  Steps:
    1. final select — boardings per day and line
#}

-- 1. Boardings per day and line.
SELECT
    service_date,
    line_name,
    estimated_boardings,
    ingested_at
FROM {{ ref('mbta_commuter_rail_boardings__base') }}
