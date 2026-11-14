"""
MBTA commuter rail boardings ingest — estimated boardings per day and line

Source:     MBTA Commuter Rail Ridership by Service Date and Line, a CSV on
            the MBTA's ArcGIS open data portal: the MBTA's daily estimates of
            boardings on each commuter rail line, from 2020-06-22 on
Cadence:    Weekly (the MBTA replaces the file irregularly, months late: on
            2026-11-14 it ran through 2026-06-24)
Each run:   Pulls the whole file (~25,000 rows, under 1 MB), so days the MBTA
            revises are captured
Writes to:  bronze.mbta_commuter_rail_boardings (append) — one row per service
            date × line per run

The figures are estimates, which the MBTA doesn't guarantee, and start after
the pandemic began; monthly figures for every mode reach back to 2018
(bronze.mbta_monthly_ridership; decision 0018).
"""

# Import standard libraries
import io
import logging

# Import third party libraries
import pandas as pd

# Import shared ingest helpers
from common.fetch import fetch
from common.load import append_to_bronze
from common.run import fail

# The file itself: "MBTA Commuter Rail Ridership by Service Date and Line".
CSV_URL = 'https://www.arcgis.com/sharing/rest/content/items/59b5c61e8e9f42f9a3745f7ad63d07d6/data'

# ── Fetch ─────────────────────────────────────────────────────────────────────

response = fetch(CSV_URL, timeout=120)
logging.info(f'Fetched the file: {len(response.content):,} bytes')

# ── Shape ─────────────────────────────────────────────────────────────────────

# Columns are read by name, renamed to project conventions; a row without a
# date or line is skipped. Boardings stay whole numbers, NULL where missing.
df = pd.read_csv(io.BytesIO(response.content), usecols=['servicedate', 'line', 'estimated_boardings'])
df = df.rename(columns={'servicedate': 'service_date'}).dropna(subset=['service_date', 'line'])
df['service_date'] = pd.to_datetime(df['service_date']).dt.date
df['estimated_boardings'] = pd.to_numeric(df['estimated_boardings'], errors='coerce').round().astype('Int64')

if df.empty:
    fail('The commuter rail ridership file held no days')

logging.info(f"Shaped {len(df)} rows, {df['service_date'].min()} to {df['service_date'].max()}, "
             f"{df['line'].nunique()} lines")

# ── Load ──────────────────────────────────────────────────────────────────────

append_to_bronze(df)
