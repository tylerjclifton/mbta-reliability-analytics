"""
Ingest: MBTA route metadata

Source:     MBTA V3 API /routes (https://api-v3.mbta.com)
Cadence:    Yearly (routes rarely change)
Each run:   Snapshots the project's rail routes (common/mbta_api.py), with
            chosen attributes rather than everything the API returns
Writes to:  bronze.mbta_routes (append) — one row per route per run
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

# The project's rail routes (common/mbta_api.py), filtered server-side.
params = {'filter[id]': ','.join(RAIL_ROUTES)}

routes = fetch(f'{API_URL}/routes', params=params, headers=api_headers(), timeout=30).json()['data']
logging.info(f'Fetched {len(routes)} routes')

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

df = pd.DataFrame(rows)
if df.empty:
    fail('The MBTA API returned none of the rail routes')

# ── Load ──────────────────────────────────────────────────────────────────────

append_to_bronze(df)
