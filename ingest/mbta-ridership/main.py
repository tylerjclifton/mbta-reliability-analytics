"""
Ingest: MBTA rail ridership (gated station entries)

Source:     MBTA Gated Station Entries, an ArcGIS open data feature service
            holding only the last two years; older days drop off it, and
            bronze keeps them from earlier runs
Cadence:    Weekly (the MBTA publishes in irregular batches, often several
            months at once and weeks to months late; July–September 2026 all
            appeared on 2026-10-20)
Each run:   Pulls everything the layer holds, not a recent window, so numbers
            the MBTA revises after the fact are captured
Writes to:  bronze.mbta_ridership (append) — one row per service date × line
            per run
Backfill:   FROM_ARCHIVE=true, set at execution time, loads the days before
            the layer's window from the MBTA's yearly archive of the same data
            instead (docs/runbook.md, decision 0015)
"""

# Import standard libraries
import datetime
import io
import json
import logging
import os
import zipfile

# Import third party libraries
import pandas as pd

# Import shared ingest helpers
from common.fetch import fetch
from common.load import append_to_bronze
from common.run import fail

# ArcGIS Feature Service endpoint for MBTA Gated Station Entries.
ARCGIS_URL = 'https://services1.arcgis.com/ceiitspzDAHrdGO1/arcgis/rest/services/GSE/FeatureServer/0/query'

# "MBTA Gated Station Entries – Historical": a zip of one CSV per calendar year
# (2014 on), at the layer's station × 30-minute period grain.
ARCHIVE_URL = 'https://www.arcgis.com/sharing/rest/content/items/7859894afb5641ce91a2bb03599fdf5b/data'

# The archive fills only days before this, the first day bronze holds from the
# layer. From it on, the layer's numbers stand: the archive's 2024 file
# undercounts October and December 2024 (decision 0015).
ARCHIVE_BEFORE = datetime.date(2024, 10, 1)

FROM_ARCHIVE = os.getenv('FROM_ARCHIVE', '').lower() == 'true'

# Rail lines as the layer names them; the Silver Line and Mattapan are out of
# scope.
TARGET_LINES = ['Red Line', 'Orange Line', 'Blue Line', 'Green Line']

# ArcGIS maxRecordCount for this service.
PAGE_SIZE = 2000

# ── Fetch ─────────────────────────────────────────────────────────────────────

if FROM_ARCHIVE:
    archive = zipfile.ZipFile(io.BytesIO(fetch(ARCHIVE_URL, timeout=300).content))
    logging.info(f'Fetched the archive: {len(archive.namelist())} files')
else:
    # The layer is at stop × time-period grain (millions of rows), so ArcGIS
    # sums entries per day and line server-side — a few thousand rows in total.
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

    # Page through the aggregated result.
    features = []
    while True:
        data = fetch(ARCGIS_URL, params={**query, 'resultOffset': len(features)}, timeout=120).json()

        # ArcGIS reports query errors in the body with HTTP 200.
        if 'error' in data:
            fail(f"ArcGIS returned an error: {data['error']}")

        page = data.get('features', [])
        features.extend(page)
        logging.info(f'Fetched {len(features)} rows so far')

        # ArcGIS sets exceededTransferLimit while more pages remain. An empty
        # page ends it too, so a stuck flag can't loop until the job times out.
        if not page or not data.get('exceededTransferLimit', False):
            break

# ── Shape ─────────────────────────────────────────────────────────────────────

if FROM_ARCHIVE:
    # Sum each year's file to day × line as it's read, the same totals the
    # layer's server-side query returns, so all years never sit in memory at
    # once. Column order varies between years, so columns are read by name.
    daily = []
    for name in sorted(n for n in archive.namelist() if n.endswith('.csv')):
        year = pd.read_csv(archive.open(name), usecols=['service_date', 'route_or_line', 'gated_entries'])
        year['service_date'] = pd.to_datetime(year['service_date']).dt.date
        year['gated_entries'] = pd.to_numeric(year['gated_entries'], errors='coerce')
        year = year[year['route_or_line'].isin(TARGET_LINES) & (year['service_date'] < ARCHIVE_BEFORE)]
        daily.append(year.groupby(['service_date', 'route_or_line'], as_index=False)['gated_entries'].sum())

    df = pd.concat(daily, ignore_index=True) if daily else pd.DataFrame()
else:
    rows = []
    for feature in features:
        attributes = feature.get('attributes', {})

        # service_date is epoch milliseconds (midnight ET expressed in UTC), so
        # the UTC calendar date is the service date; a
        # row without one is skipped.
        service_date_ms = attributes.get('service_date')
        if not isinstance(service_date_ms, (int, float)):
            continue

        rows.append({
            'service_date':  datetime.datetime.fromtimestamp(service_date_ms / 1000, tz=datetime.timezone.utc).date(),
            'route_or_line': attributes.get('route_or_line'),
            'gated_entries': float(attributes.get('gated_entries') or 0),
        })

    df = pd.DataFrame(rows)

if df.empty:
    fail(f'The archive held no rail days before {ARCHIVE_BEFORE}' if FROM_ARCHIVE
         else 'The ArcGIS layer returned no rail days')

logging.info(f"Shaped {len(df)} rows, {df['service_date'].min()} to {df['service_date'].max()}")

# ── Load ──────────────────────────────────────────────────────────────────────

append_to_bronze(df)
