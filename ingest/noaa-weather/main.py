"""
NOAA weather ingest — daily weather at Boston Logan

Source:     NOAA GHCN-Daily station file for USW00014739 (NCEI): one CSV of the
            station's full daily history (1936 onward), refreshed daily and
            typically 2–3 days behind
Cadence:    Daily
Each run:   Re-pulls the last LOOKBACK_DAYS days (default 10), since NOAA
            revises recent days as they pass quality control
Writes to:  bronze.noaa_weather (append) — one row per observation date per run
Backfill:   LOOKBACK_DAYS set higher at execution time (docs/runbook.md)

Values stay in GHCN source units with their quality flags; silver converts
units and drops values that failed quality control.
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

# Boston Logan International Airport.
STATION_ID = 'USW00014739'
GHCN_URL = f'https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{STATION_ID}.csv'

# GHCN elements kept: max/min temperature (tenths of °C), precipitation
# (tenths of mm, liquid equivalent incl. melted snow), and snowfall (mm).
ELEMENTS = ['TMAX', 'TMIN', 'PRCP', 'SNOW']

# Re-pull window start.
LOOKBACK_DAYS = int(os.getenv('LOOKBACK_DAYS', '10'))
start_date = datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)

# ── Fetch ─────────────────────────────────────────────────────────────────────

csv_text = fetch(GHCN_URL, timeout=120).text
logging.info(f'Fetched the GHCN-Daily file for {STATION_ID}')

# ── Shape ─────────────────────────────────────────────────────────────────────

# Read only the date and the kept elements plus their flag columns. Read as
# strings: values are space-padded and may be empty.
columns = ['DATE'] + [column for element in ELEMENTS for column in (element, f'{element}_ATTRIBUTES')]
raw = pd.read_csv(io.StringIO(csv_text), usecols=columns, dtype=str)

# Filter to the re-pull window.
raw['DATE'] = pd.to_datetime(raw['DATE']).dt.date
raw = raw[raw['DATE'] >= start_date]

# Rename to bronze columns; values become nullable integers.
df = pd.DataFrame({'station_id': STATION_ID, 'observation_date': raw['DATE']})
for element in ELEMENTS:
    df[element.lower()] = pd.to_numeric(raw[element].str.strip(), errors='coerce').astype('Int64')
    df[f'{element.lower()}_attributes'] = raw[f'{element}_ATTRIBUTES']

if not df.empty:
    logging.info(f"Shaped {len(df)} rows, {df['observation_date'].min()} to {df['observation_date'].max()}")

# ── Load ──────────────────────────────────────────────────────────────────────

append_to_bronze(df)
