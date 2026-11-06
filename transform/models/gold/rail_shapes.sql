{#
  gold.rail_shapes — one row per canonical shape × route

  The official path of each rail route, with the line it belongs to, so the
  dashboard can draw the lines on the map and filter them with the line selector.
  Each pattern has one shape per direction; both are kept, since the tracks can
  run apart. The dashboard decodes the polyline (helpers.decode_polyline).

  Steps:
    1. final select — canonical shapes with their route's line
#}

-- 1. Canonical shapes only: one official path per pattern and direction
SELECT
    s.shape_id,
    s.route_id,
    r.line_name,
    s.shape_polyline,
    s.ingested_at
FROM {{ ref('mbta_shapes__base') }} AS s
INNER JOIN {{ ref('mbta_routes__base') }} AS r
    ON s.route_id = r.route_id
WHERE s.is_canonical
