"""
Ingest: MBTA rail ridership (gated station entries)

Source:     MBTA Gated Station Entries, ArcGIS open data feature service
Cadence:    Weekly — the MBTA publishes new months with a ~1–2 month lag
Each run:   Pulls the full published history (2024-10 onward), not a recent
            window, so any numbers the MBTA revises after the fact are captured
Writes to:  bronze.mbta_ridership (append) — one row per service date × line per run
"""

# Import standard libraries
import datetime
import json
import logging

# Import third party libraries
import pandas

# Import shared ingest helpers
from common.bronze import append_to_bronze, fail, fetch

# ArcGIS Feature Service endpoint for MBTA Gated Station Entries
ARCGIS_URL = 'https://services1.arcgis.com/ceiitspzDAHrdGO1/arcgis/rest/services/GSE/FeatureServer/0/query'

# Target lines — Silver Line and Mattapan excluded intentionally
TARGET_LINES = ['Red Line', 'Orange Line', 'Blue Line', 'Green Line']

# ArcGIS maxRecordCount for this service
PAGE_SIZE = 2000

# ── Fetch ─────────────────────────────────────────────────────────────────────

# The layer is at stop × time-period grain (millions of rows), so ArcGIS sums
# entries per day and line server-side — a few thousand rows in total.
# gated_entries is stored as a string, so it's cast before summing.
query = {
    'where': "route_or_line IN ('" + "', '".join(TARGET_LINES) + "')",
    'groupByFieldsForStatistics': 'service_date,route_or_line',
    'outStatistics': json.dumps([{
        'statisticType': 'sum',
        'onStatisticField': 'CAST(gated_entries AS FLOAT)',
        'outStatisticFieldName': 'gated_entries',
    }]),
    'orderByFields': 'service_date ASC,route_or_line ASC',
    'resultRecordCount': PAGE_SIZE,
    'f': 'json',
}

# Page through the aggregated result
features = []
while True:
    data = fetch(ARCGIS_URL, params={**query, 'resultOffset': len(features)}, timeout=120).json()

    # ArcGIS reports query errors in the body with HTTP 200
    if 'error' in data:
        fail(f"ArcGIS API error: {data['error']}")

    features.extend(data.get('features', []))
    logging.info(f"Fetched {len(features)} records so far...")

    # ArcGIS sets exceededTransferLimit while more pages remain
    if not data.get('exceededTransferLimit', False):
        break

# ── Shape ─────────────────────────────────────────────────────────────────────

rows = []
for feature in features:
    attributes = feature.get('attributes', {})

    # service_date is epoch milliseconds (midnight ET expressed in UTC), so the
    # UTC calendar date is the service date
    service_date_ms = attributes.get('service_date')
    if not isinstance(service_date_ms, (int, float)):
        continue

    rows.append({
        'service_date':  datetime.datetime.fromtimestamp(service_date_ms / 1000, tz=datetime.timezone.utc).date(),
        'route_or_line': attributes.get('route_or_line'),
        'gated_entries': float(attributes.get('gated_entries') or 0),
    })

df = pandas.DataFrame(rows)
if not df.empty:
    logging.info(f"Pulled {df['service_date'].min()} to {df['service_date'].max()}")

# ── Write ─────────────────────────────────────────────────────────────────────

append_to_bronze(df)
