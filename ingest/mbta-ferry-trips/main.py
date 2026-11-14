"""
MBTA ferry trips ingest — every ferry trip, its riders and its times

Source:     MBTA Ferry Daily Ridership by Trip, Route, and Stop, an ArcGIS open
            data feature service: one row per trip leg from 2018-11 on, with
            riders on and off and the scheduled and actual departure and
            arrival, so it measures the ferry's punctuality as well as its use
Cadence:    Weekly (the MBTA updates it irregularly, months late: on
            2026-11-13 it ran through 2026-03-31)
Each run:   Re-pulls the last LOOKBACK_DAYS days of service (default 365), so
            months published late or revised are captured without re-reading
            all ~400,000 rows every week
Writes to:  bronze.mbta_ferry_trips (append) — one row per trip leg per run
Backfill:   LOOKBACK_DAYS=4000, set at execution time, pulls the whole layer
            (docs/runbook.md)

Values are kept as published (decision 0018): actual times and rider counts
are text ("2026-03-31 09:45", "8"; "NA" when missing), and riders off are
negative.
"""

# Import standard libraries
import datetime
import logging
import os

# Import third party libraries
import pandas as pd

# Import shared ingest helpers
from common.fetch import fetch
from common.load import append_to_bronze
from common.run import fail

# ArcGIS Feature Service endpoint for MBTA Ferry Daily Ridership by Trip,
# Route, and Stop.
ARCGIS_URL = ('https://services1.arcgis.com/ceiitspzDAHrdGO1/arcgis/rest/services/'
              'MBTA_Ferry_Daily_Ridership_by_Trip_Route_and_Stop/FeatureServer/0/query')

# Days of service re-pulled each run, counted back from today.
LOOKBACK_DAYS = int(os.getenv('LOOKBACK_DAYS', '365'))

# ArcGIS maxRecordCount for this service.
PAGE_SIZE = 2000

# The layer's columns, in its order, without its row number (ObjectId).
COLUMNS = [
    'service_date', 'route_id', 'route_name', 'trip_freq', 'trip_freq_adj', 'sub_route', 'trip_id', 'stop_id',
    'departure_terminal', 'mbta_sched_departure', 'actual_departure', 'pax_on', 'pax_load', 'pax_off',
    'mbta_sched_arrival', 'actual_arrival', 'arrival_terminal', 'vessel_time_slot', 'trip_endpoint',
    'travel_direction',
]

# Date fields arrive as epoch milliseconds: service_date the day at midnight
# ET, the scheduled times true instants.
TIMESTAMP_COLUMNS = ['mbta_sched_departure', 'mbta_sched_arrival']

# ── Fetch ─────────────────────────────────────────────────────────────────────

since = datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)
query = {
    'where': f"service_date >= DATE '{since}'",
    'outFields': ','.join(COLUMNS),
    'orderByFields': 'service_date ASC,ObjectId ASC',
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

# A row without a service date is skipped.
rows = [feature.get('attributes', {}) for feature in features]
rows = [row for row in rows if isinstance(row.get('service_date'), (int, float))]

if not rows:
    fail(f'The ArcGIS layer returned no ferry trips since {since}')

df = pd.DataFrame(rows).reindex(columns=COLUMNS)

# service_date is midnight ET in UTC, so the UTC calendar date is the service
# date; the scheduled times are instants.
df['service_date'] = pd.to_datetime(df['service_date'], unit='ms', utc=True).dt.date
for column in TIMESTAMP_COLUMNS:
    df[column] = pd.to_datetime(df[column], unit='ms', utc=True)

logging.info(f"Shaped {len(df)} rows, {df['service_date'].min()} to {df['service_date'].max()}")

# ── Load ──────────────────────────────────────────────────────────────────────

append_to_bronze(df)
