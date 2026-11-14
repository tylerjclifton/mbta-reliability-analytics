{#
  silver.mbta_commuter_rail_boardings__base — one row per service date × line

  The MBTA's estimated commuter rail boardings per day and line, as of the
  latest pull: every run re-pulls the whole file, so keeping the latest lets
  revisions win, while bronze keeps the originals. Estimates, from 2020-06-22
  on (decision 0018).

  Steps:
    1. latest_versions — latest pull per service date × line
    2. final select    — rename to project conventions
#}

WITH

    -- 1. Latest pull per service date × line.
    latest_versions AS (
        SELECT *
        FROM {{ source('bronze', 'mbta_commuter_rail_boardings') }}
        {{ keep_latest_version(['service_date', 'line']) }}
    )

-- 2. Project conventions.
SELECT
    service_date,
    line                AS line_name,
    estimated_boardings,
    ingested_at,
    ingested_by
FROM latest_versions
