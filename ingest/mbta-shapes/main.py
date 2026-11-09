"""
MBTA shapes ingest — the path each rail route's trains follow

Source:     MBTA V3 API /shapes (https://api-v3.mbta.com)
Cadence:    Weekly (shapes rarely change; a new or rerouted stretch of track is
            picked up within a week)
Each run:   For each rail route, snapshots every shape the API returns: its
            canonical paths and their variants
Writes to:  bronze.mbta_shapes (append) — one row per shape × route per run

The API doesn't say which route a shape belongs to, so route_id is the route
that was requested. polyline is the path in Google's encoded polyline format, as
the API returned it.
"""

# Import standard libraries
import logging

# Import third party libraries
import pandas as pd

# Import shared ingest helpers
from common.fetch import fetch
from common.load import append_to_bronze
from common.mbta_api import API_URL, RAIL_ROUTES, api_headers
from common.run import fail

# ── Fetch ─────────────────────────────────────────────────────────────────────

# One request per rail route (common/mbta_api.py). Silver reads only the latest
# run, so a route with no shapes fails the job before anything loads: a partial
# snapshot would erase that line from the map.
shapes_by_route = {}
for route_id in RAIL_ROUTES:
    params = {'filter[route]': route_id}
    shapes = fetch(f'{API_URL}/shapes', params=params, headers=api_headers(), timeout=30).json()['data']
    if not shapes:
        fail(f'The MBTA API returned no shapes for route {route_id}')

    shapes_by_route[route_id] = shapes
    logging.info(f'Fetched {route_id}: {len(shapes)} shapes')

# ── Shape ─────────────────────────────────────────────────────────────────────

rows = []
for route_id, shapes in shapes_by_route.items():
    for shape in shapes:
        attributes = shape.get('attributes', {})
        rows.append({
            'route_id': route_id,
            'shape_id': shape.get('id'),
            'polyline': attributes.get('polyline'),
        })

# ── Load ──────────────────────────────────────────────────────────────────────

append_to_bronze(pd.DataFrame(rows))
