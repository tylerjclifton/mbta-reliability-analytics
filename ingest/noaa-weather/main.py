"""
Ingest: NOAA daily weather at Boston Logan

Source:     NOAA GHCN-Daily station file for USW00014739 (NCEI). One CSV holds
            the station's full daily history (1936 onward), refreshed daily,
            typically 2–3 days behind the current date.
Cadence:    Daily
Each run:   Re-pulls the last LOOKBACK_DAYS days (default 10) — NOAA revises
            recent days as they pass quality control. Set LOOKBACK_DAYS higher
            at execution time to backfill.
Writes to:  bronze.noaa_weather (append) — one row per observation date per run

Values are kept in GHCN source units with their quality flags; unit conversion
and QC filtering happen in silver.
"""

# Import standard libraries
import datetime
import io
import logging
import os

# Import third party libraries
import pandas

# Import shared ingest helpers
from common.bronze import append_to_bronze, fetch

# Boston Logan International Airport
STATION_ID = 'USW00014739'
GHCN_URL = f'https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{STATION_ID}.csv'

# GHCN elements kept: max/min temperature (tenths of °C), precipitation
# (tenths of mm, liquid equivalent incl. melted snow), and snowfall (mm)
ELEMENTS = ['TMAX', 'TMIN', 'PRCP', 'SNOW']

# Re-pull window start
LOOKBACK_DAYS = int(os.getenv('LOOKBACK_DAYS', '10'))
start_date = datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)

# ── Fetch ─────────────────────────────────────────────────────────────────────

logging.info(f"Fetching GHCN-Daily for {STATION_ID} from {start_date}")
csv_text = fetch(GHCN_URL, timeout=120).text

# ── Shape ─────────────────────────────────────────────────────────────────────

# Read only the date and the kept elements plus their flag columns. Read as
# strings: values are space-padded and may be empty.
columns = ['DATE'] + [column for element in ELEMENTS for column in (element, f'{element}_ATTRIBUTES')]
raw = pandas.read_csv(io.StringIO(csv_text), usecols=columns, dtype=str)

# Filter to the re-pull window
raw['DATE'] = pandas.to_datetime(raw['DATE']).dt.date
raw = raw[raw['DATE'] >= start_date]

# Rename to bronze columns; values become nullable integers
df = pandas.DataFrame({'station_id': STATION_ID, 'observation_date': raw['DATE']})
for element in ELEMENTS:
    df[element.lower()] = pandas.to_numeric(raw[element].str.strip(), errors='coerce').astype('Int64')
    df[f'{element.lower()}_attributes'] = raw[f'{element}_ATTRIBUTES']

if not df.empty:
    logging.info(f"Pulled {df['observation_date'].min()} to {df['observation_date'].max()}")

# ── Write ─────────────────────────────────────────────────────────────────────

append_to_bronze(df)
