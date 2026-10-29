"""
Ingest: MBTA route metadata

Source:     MBTA V3 API /routes (https://api-v3.mbta.com)
Cadence:    Yearly (routes rarely change)
Each run:   Snapshots the full list of rail routes
Writes to:  bronze.mbta_routes (append) — one row per route per run
"""

# Import standard libraries
import logging

# Import third party libraries
import pandas

# Import shared ingest helpers
from common.fetch import fetch
from common.load import append_to_bronze
from common.mbta_api import API_URL, RAIL_ROUTES, api_params

# ── Fetch ─────────────────────────────────────────────────────────────────────

# The project's rail routes (common/mbta_api.py), filtered server-side
params = api_params({'filter[id]': ','.join(RAIL_ROUTES)})

routes = fetch(f'{API_URL}/routes', params=params, timeout=30).json()['data']

# ── Shape ─────────────────────────────────────────────────────────────────────

rows = []
for route in routes:
    attributes = route.get('attributes', {})
    destinations = attributes.get('direction_destinations')
    rows.append({
        'route_id':               route.get('id'),
        'long_name':              attributes.get('long_name'),
        'route_type':             attributes.get('type'),
        'color':                  attributes.get('color'),
        'description':            attributes.get('description'),
        'direction_destinations': str(destinations) if destinations else None,
    })

logging.info(f"{len(rows)} routes in response")

# ── Load ──────────────────────────────────────────────────────────────────────

append_to_bronze(pandas.DataFrame(rows))
