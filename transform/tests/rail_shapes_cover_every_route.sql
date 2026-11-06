{{ config(severity='warn') }}

-- Every rail route has a line to draw on the map. Fails with one row per route
-- that has none, as it would if the MBTA stopped marking shapes canonical. A
-- warning: the data is fine, and the map still shows the stations.
SELECT r.route_id
FROM {{ ref('mbta_routes__base') }} AS r
LEFT JOIN {{ ref('rail_shapes') }} AS s
    ON r.route_id = s.route_id
WHERE s.route_id IS NULL
