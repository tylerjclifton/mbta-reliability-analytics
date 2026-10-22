{#
  silver.mbta_ridership — one row per service date × line

  Every ingest run re-pulls the full ArcGIS history, so bronze holds one
  version of each day per run. Keeping the latest means any revisions the MBTA
  publishes replace earlier numbers, while bronze still has the originals.

  Steps:
    1. latest_versions — latest pull per service date × line
    2. final select    — rename to project conventions
#}

WITH

    -- 1. Latest pull per service date × line
    latest_versions AS (
        SELECT *
        FROM {{ source('bronze', 'mbta_ridership') }}
        {{ keep_latest_version(['service_date', 'route_or_line']) }}
    )

-- 2. Project conventions: line_name matches silver.mbta_routes
SELECT
    service_date,
    route_or_line                                               AS line_name,
    gated_entries,
    ingested_at,
    ingested_by
FROM latest_versions
