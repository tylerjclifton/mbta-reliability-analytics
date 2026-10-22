"""
Ingest: MBTA route metadata

Source:     MBTA V3 API /routes (https://api-v3.mbta.com)
Cadence:    Yearly (routes rarely change)
Each run:   Snapshots the full list of rail routes
Writes to:  bronze.mbta_routes (append) — one row per route per run
"""

# Import standard libraries
import logging
import os

# Import third party libraries
import pandas

# Import shared ingest helpers
from common.bronze import append_to_bronze, fetch

# Rail routes to snapshot — must match the alerts job's TARGET_ROUTES
TARGET_ROUTES = ['Red', 'Blue', 'Orange', 'Green-B', 'Green-C', 'Green-D', 'Green-E']

# ── Fetch ─────────────────────────────────────────────────────────────────────

# Filter to target routes server-side; the API key is optional but removes the
# anonymous rate limit
params = {'filter[id]': ','.join(TARGET_ROUTES)}
if os.getenv('MBTA_API_KEY'):
    params['api_key'] = os.getenv('MBTA_API_KEY')

routes = fetch('https://api-v3.mbta.com/routes', params=params, timeout=30).json()['data']

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

# ── Write ─────────────────────────────────────────────────────────────────────

append_to_bronze(pandas.DataFrame(rows))
