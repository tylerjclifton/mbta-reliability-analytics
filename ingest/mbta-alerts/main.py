"""
Ingest: MBTA service alerts

Source:     MBTA V3 API /alerts (https://api-v3.mbta.com)
Cadence:    Every 15 minutes
Each run:   Snapshots the whole live feed: every mode (subway, bus, commuter
            rail, ferry) and every effect (incl. elevator closures and
            notices). Silver keeps rail and service-affecting alerts; bronze
            stays complete (decision 0011)
Writes to:  bronze.mbta_alerts (append) — one row per alert per run: the
            alert's full JSON exactly as the API returned it

The API only shows alerts that are active or upcoming; once an alert ends it
disappears for good. Bronze's snapshots are therefore the only record of past
alerts, and silver uses the last run an alert was seen in to tell when it ended
(whichever comes first: that, or the end time the MBTA posted).

Each alert is stored whole rather than as chosen columns, and the whole feed
is requested (no route filter, every activity), so new questions never depend
on what this script happened to keep. Filtering to rail and splitting alerts into one row per
route happen in silver (mbta_alerts__by_route). Until 2026-10-24 this job
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

# ── Fetch ─────────────────────────────────────────────────────────────────────

# The whole feed: no route filter, and every activity. Without filter[activity]
# the API documents a default of BOARD/EXIT/RIDE, which would drop alerts that
# only affect escalators, elevators, parking, or bikes (a route filter does
# apply it); ALL is the documented way to get everything. The API key is
# optional but removes the anonymous rate limit.
params = {'filter[activity]': 'ALL'}
if os.getenv('MBTA_API_KEY'):
    params['api_key'] = os.getenv('MBTA_API_KEY')

alerts = fetch('https://api-v3.mbta.com/alerts', params=params, timeout=30).json()['data']

# ── Shape ─────────────────────────────────────────────────────────────────────

# One row per alert: its ID, and the whole alert as compact JSON (key order kept)
rows = [{'alert_id': alert.get('id'), 'alert_json': json.dumps(alert, separators=(',', ':'))}
        for alert in alerts]

logging.info(f"{len(rows)} alerts in feed")

# ── Write ─────────────────────────────────────────────────────────────────────

append_to_bronze(pandas.DataFrame(rows))
