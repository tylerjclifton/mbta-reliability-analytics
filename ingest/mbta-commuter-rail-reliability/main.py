"""
MBTA commuter rail reliability ingest — trains on time and canceled, by line

Source:     MBTA Commuter Rail Reliability, a CSV on the MBTA's ArcGIS open
            data portal: for each service date, line, and peak or off-peak
            period, the trains measured, those on time, and those canceled,
            from 2016-01-01 on
Cadence:    Weekly (the MBTA replaces the file about weekly: on 2026-11-14 it
            ran through 2026-10-31)
Each run:   Downloads the whole file (~13 MB, ~110,000 rows) and keeps the last
            LOOKBACK_DAYS days of service (default 120), so days revised after
            publication are captured without loading every row every week
Writes to:  bronze.mbta_commuter_rail_reliability (append) — one row per row of
            the file per run
Backfill:   LOOKBACK_DAYS=4000, set at execution time, loads the whole file
            (docs/runbook.md)

Rows are kept as published (decision 0019), one column's spelling aside. A
line can have several rows for one day and period: branches published as
parts of it, sometimes under the same name, so nothing in a row is unique.
The MBTA publishes numerators and denominators separately so they can be
summed across rows before dividing.
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

# The file itself: "MBTA Commuter Rail Reliability".
CSV_URL = 'https://www.arcgis.com/sharing/rest/content/items/ec18161c237d419698abc767f1be6a50/data'

# Days of service kept each run, counted back from today.
LOOKBACK_DAYS = int(os.getenv('LOOKBACK_DAYS', '120'))

# The file's columns as it names them, text then counts, in its order.
TEXT_COLUMNS = [
    'gtfs_route_id', 'gtfs_route_short_name', 'gtfs_route_long_name', 'gtfs_route_desc', 'route_category',
    'mode_type', 'peak_offpeak_ind', 'metric_type',
]
COUNT_COLUMNS = ['otp_numerator', 'otp_denominator', 'cancelled_numerator']  # spelling: as published

# The one column renamed, once it's typed: American spelling, as for every
# name in the project.
RENAMES = {'cancelled_numerator': 'canceled_numerator'}  # spelling: as published

# ── Fetch ─────────────────────────────────────────────────────────────────────

response = fetch(CSV_URL, timeout=300)
logging.info(f'Fetched the file: {len(response.content):,} bytes')

# ── Shape ─────────────────────────────────────────────────────────────────────

# Columns are read by name, as text so "NA" stays as published; a row without
# a date is skipped. Counts stay whole numbers, NULL where missing. Only the
# lookback window is kept.
df = pd.read_csv(io.BytesIO(response.content), usecols=['service_date', *TEXT_COLUMNS, *COUNT_COLUMNS],
                 dtype=str, keep_default_na=False)
df = df[df['service_date'] != '']
df['service_date'] = pd.to_datetime(df['service_date'], format='%m/%d/%Y').dt.date
for column in COUNT_COLUMNS:
    df[column] = pd.to_numeric(df[column], errors='coerce').astype('Int64')

since = datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)
df = df[df['service_date'] >= since].reset_index(drop=True).rename(columns=RENAMES)

if df.empty:
    fail(f'The commuter rail reliability file held no days since {since}')

logging.info(f"Shaped {len(df)} rows, {df['service_date'].min()} to {df['service_date'].max()}, "
             f"{df['gtfs_route_id'].nunique()} lines")

# ── Load ──────────────────────────────────────────────────────────────────────

append_to_bronze(df)
