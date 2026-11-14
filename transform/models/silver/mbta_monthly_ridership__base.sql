{#
  silver.mbta_monthly_ridership__base — one row per month × day type × mode/line

  The MBTA's monthly ridership figures, every mode and line, as of the latest
  pull: every run re-pulls the whole layer, so bronze holds one version of each
  row per run, and keeping the latest lets revisions win. Rows stay as
  published, subtotals included (Heavy Rail, Light Rail, All Bus, day type
  Total); gold.transit_ridership keeps the ones that don't overlap (decision
  0018). They count boardings, a ride with a transfer counting twice, so they
  don't compare with gated entries.

  Steps:
    1. latest_versions — latest pull per month × day type × mode or line
    2. final select    — rename to project conventions
#}

WITH

    -- 1. Latest pull per month × day type × mode or line.
    latest_versions AS (
        SELECT *
        FROM {{ source('bronze', 'mbta_monthly_ridership') }}
        {{ keep_latest_version(['month_of_service', 'daytype', 'route_or_line']) }}
    )

-- 2. Project conventions.
SELECT
    month_of_service  AS month_start,
    daytype           AS day_type,
    daycount          AS day_count,
    route_or_line     AS mode_or_line,
    ridership_total   AS riders_total,
    ridership_average AS riders_per_day,
    ingested_at,
    ingested_by
FROM latest_versions
