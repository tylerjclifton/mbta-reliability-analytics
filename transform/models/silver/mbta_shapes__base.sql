{#
  silver.mbta_shapes__base — one row per shape × route

  Every shape of each rail route in the latest snapshot: the path its trains
  follow, in Google's encoded polyline format. Canonical shapes are the route's
  official paths; the others are variants.

  This keeps the latest run's rows, not each key's latest row as the routes and
  stops models do. Shape IDs can change when the MBTA reissues its schedule, and
  a retired shape would otherwise stay on the map for good. The ingest fails
  rather than load a partial snapshot, so the latest run is always complete.

  Steps:
    1. final select — the latest run, renamed to project conventions, with
                      canonical shapes flagged
#}

-- 1. The latest run's rows.
SELECT
    shape_id,
    route_id,
    polyline                            AS shape_polyline,
    STARTS_WITH(shape_id, 'canonical-') AS is_canonical,
    ingested_at,
    ingested_by
FROM {{ source('bronze', 'mbta_shapes') }}
WHERE ingested_at = (SELECT MAX(latest.ingested_at) FROM {{ source('bronze', 'mbta_shapes') }} AS latest)
