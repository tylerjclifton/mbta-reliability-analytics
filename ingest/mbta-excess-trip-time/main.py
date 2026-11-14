"""
MBTA excess trip time ingest — riders' subway trips against a normal trip

Source:     MBTA Heavy Rail Excess Trip Time, a CSV on the MBTA's ArcGIS open
            data portal: for each service date, half hour, line, and direction
            on the Red, Orange, and Blue Lines, the MBTA's estimate of how many
            rode and how long their trips (wait plus travel) took against a
            baseline, from 2022-01-01 on
Cadence:    Weekly (the MBTA replaces the file about weekly, weeks late: on
            2026-11-14 it ran through 2026-09-30)
Each run:   Downloads the whole file (~95 MB, ~390,000 rows) and keeps the last
            LOOKBACK_DAYS days of service (default 120), so days published
            late or revised are captured without loading every row every week
Writes to:  bronze.mbta_excess_trip_time (append) — one row per service date ×
            half hour × line × direction per run
Backfill:   LOOKBACK_DAYS=4000, set at execution time, loads the whole file
            (docs/runbook.md)

Values are kept as published (decision 0019): the minutes and the riders
within each threshold are totals over the group's estimated riders, to be
divided by them.
"""

# Import standard libraries
import datetime
import io
import logging
import os

# Import third party libraries
import pandas as pd

# Import shared ingest helpers
from common.fetch import fetch
from common.load import append_to_bronze
from common.run import fail

# The file itself: "MBTA Heavy Rail Excess Trip Time".
CSV_URL = 'https://www.arcgis.com/sharing/rest/content/items/031c3392b4fd46baad54fcceb9fb4254/data'

# Days of service kept each run, counted back from today.
LOOKBACK_DAYS = int(os.getenv('LOOKBACK_DAYS', '120'))

# The file's columns, in its order.
COLUMNS = [
    'svc_date', 'day', 'halfhour', 'peak', 'route_id', 'dir_id', 'est_pax',
    'weighted_bl_trip_time', 'weighted_bl_wait_time', 'weighted_bl_travel_time',
    'weighted_trip_time', 'weighted_wait_time', 'weighted_travel_time',
    'five_min_thresh', 'twenty_min_thresh', 'twenty_pct_thresh', 'thirty_pct_thresh',
]

# Columns that hold text; every other column but the date is a number.
TEXT_COLUMNS = ['day', 'halfhour', 'peak', 'route_id', 'dir_id']

# ── Fetch ─────────────────────────────────────────────────────────────────────

response = fetch(CSV_URL, timeout=300)
logging.info(f'Fetched the file: {len(response.content):,} bytes')

# ── Shape ─────────────────────────────────────────────────────────────────────

# Columns are read by name, the date renamed to project conventions; a row
# without a date is skipped. Only the lookback window is kept.
df = pd.read_csv(io.BytesIO(response.content), usecols=COLUMNS, dtype={c: str for c in TEXT_COLUMNS})
df = df.rename(columns={'svc_date': 'service_date'}).dropna(subset=['service_date'])
df['service_date'] = pd.to_datetime(df['service_date']).dt.date

since = datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)
df = df[df['service_date'] >= since].reset_index(drop=True)

if df.empty:
    fail(f'The excess trip time file held no days since {since}')

logging.info(f"Shaped {len(df)} rows, {df['service_date'].min()} to {df['service_date'].max()}")

# ── Load ──────────────────────────────────────────────────────────────────────

append_to_bronze(df)
