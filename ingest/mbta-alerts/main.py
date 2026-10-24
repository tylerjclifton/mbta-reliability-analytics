"""
Ingest: MBTA service alerts

Source:     MBTA V3 API /alerts (https://api-v3.mbta.com)
Cadence:    Every 15 minutes
Each run:   Snapshots every rail alert currently in the live feed, including
            ones that don't affect train service (e.g. elevator closures,
            notices) — silver filters those out, so bronze stays complete
Writes to:  bronze.mbta_alerts_raw (append) — one row per alert per run: the
            alert's full JSON exactly as the API returned it

The API only shows alerts that are active or upcoming; once an alert ends it
disappears for good. Bronze's snapshots are therefore the only record of past
alerts, and silver uses the last run an alert was seen in to tell when it ended
(whichever comes first: that, or the end time the MBTA posted).

Each alert is stored whole rather than as chosen columns, so new questions
never depend on what this script happened to keep. Splitting alerts into one
row per route happens in silver (mbta_alerts__base). Until 2026-10-24 this job
wrote only chosen columns to a table now named bronze.mbta_alerts_legacy, which
dropped the stops each alert affects and more; it's kept, frozen, as history
(decision 0002).
"""

# Import standard libraries
import json
import logging
import os

# Import third party libraries
import pandas

# Import shared ingest helpers
from common.bronze import append_to_bronze, fetch

# Rail routes to snapshot — Silver Line, Mattapan, buses, and ferries excluded.
# Must match rail_routes in silver/mbta_alerts__base.sql.
TARGET_ROUTES = ['Red', 'Blue', 'Orange', 'Green-B', 'Green-C', 'Green-D', 'Green-E']

# ── Fetch ─────────────────────────────────────────────────────────────────────

# Filter to target routes server-side; the API key is optional but removes the
# anonymous rate limit
params = {'filter[route]': ','.join(TARGET_ROUTES)}
if os.getenv('MBTA_API_KEY'):
    params['api_key'] = os.getenv('MBTA_API_KEY')

alerts = fetch('https://api-v3.mbta.com/alerts', params=params, timeout=30).json()['data']

# ── Shape ─────────────────────────────────────────────────────────────────────

# One row per alert: its ID, and the whole alert as compact JSON (key order kept)
rows = [{'alert_id': alert.get('id'), 'alert_json': json.dumps(alert, separators=(',', ':'))}
        for alert in alerts]

logging.info(f"{len(rows)} rail alerts in feed")

# ── Write ─────────────────────────────────────────────────────────────────────

# The table isn't the job's default name (mbta_alerts), so it's named
# explicitly; Terraform sets the same value
append_to_bronze(pandas.DataFrame(rows), table_id=os.getenv('BQ_TABLE_ID', 'mbta_alerts_raw'))
