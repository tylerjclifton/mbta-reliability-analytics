"""
MBTA mode ridership ingest — monthly riders on every mode and line

Source:     MBTA Monthly Ridership by Mode and Line, an ArcGIS open data
            feature service: what the MBTA reports to the National Transit
            Database, from 2018-07 on
Cadence:    Weekly (the MBTA adds each month weeks after it ends)
Each run:   Pulls the whole layer (~5,000 rows), so months the MBTA revises
            after the fact are captured
Writes to:  bronze.mbta_mode_ridership (append) — one row per month × day type
            × mode or line per run

The layer counts unlinked trips (a ride with a transfer counts twice), on
every mode, so its subway figures run higher than gated entries
(bronze.mbta_ridership) and don't compare with them. Rows are kept as
published, subtotals included: "Heavy Rail" is Red + Orange + Blue, "Light
Rail" Green + Mattapan, "All Bus" Bus + Silver Line (+ the retired private
carrier and trackless trolley routes), and day type "Total" the month's
weekdays, Saturdays, and Sundays together (decision 0018).
"""

# Import standard libraries
import datetime
import logging

# Import third party libraries
import pandas as pd

# Import shared ingest helpers
from common.fetch import fetch
from common.load import append_to_bronze
from common.run import fail

# ArcGIS Feature Service endpoint for MBTA Monthly Ridership by Mode and Line.
ARCGIS_URL = 'https://services1.arcgis.com/ceiitspzDAHrdGO1/arcgis/rest/services/NTD_Reporting/FeatureServer/0/query'

# ArcGIS maxRecordCount for this service.
PAGE_SIZE = 1000

# ── Fetch ─────────────────────────────────────────────────────────────────────

query = {
    'where': '1=1',
    'outFields': 'month_of_service,daytype,daycount,route_or_line,ridership_total,ridership_average',
    'orderByFields': 'month_of_service ASC,route_or_line ASC,daytype ASC',
    'resultRecordCount': PAGE_SIZE,
    'f': 'json',
}

features = []
while True:
    data = fetch(ARCGIS_URL, params={**query, 'resultOffset': len(features)}, timeout=120).json()

    # ArcGIS reports query errors in the body with HTTP 200.
    if 'error' in data:
        fail(f"ArcGIS returned an error: {data['error']}")

    page = data.get('features', [])
    features.extend(page)
    logging.info(f'Fetched {len(features)} rows so far')

    # ArcGIS sets exceededTransferLimit while more pages remain. An empty page
    # ends it too, so a stuck flag can't loop until the job times out.
    if not page or not data.get('exceededTransferLimit', False):
        break

# ── Shape ─────────────────────────────────────────────────────────────────────

rows = []
for feature in features:
    attributes = feature.get('attributes', {})

    # month_of_service is epoch milliseconds (the 1st at midnight ET, expressed
    # in UTC), so the UTC calendar date is the month's first day; a row without
    # one is skipped.
    month_ms = attributes.get('month_of_service')
    if not isinstance(month_ms, (int, float)):
        continue

    rows.append({
        'month_of_service':  datetime.datetime.fromtimestamp(month_ms / 1000, tz=datetime.timezone.utc).date(),
        'daytype':           attributes.get('daytype'),
        'daycount':          attributes.get('daycount'),
        'route_or_line':     attributes.get('route_or_line'),
        'ridership_total':   attributes.get('ridership_total'),
        'ridership_average': attributes.get('ridership_average'),
    })

if not rows:
    fail('The ArcGIS layer returned no months')

# Counts stay whole numbers, NULL where the layer has none.
df = pd.DataFrame(rows).astype({'daycount': 'Int64', 'ridership_total': 'Int64', 'ridership_average': 'Int64'})

logging.info(f"Shaped {len(df)} rows, {df['month_of_service'].min()} to {df['month_of_service'].max()}, "
             f"{df['route_or_line'].nunique()} modes and lines")

# ── Load ──────────────────────────────────────────────────────────────────────

append_to_bronze(df)
