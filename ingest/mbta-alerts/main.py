"""
Ingest: MBTA service alerts

Source:     MBTA V3 API /alerts (https://api-v3.mbta.com)
Cadence:    Every 15 minutes
Each run:   Snapshots the whole live feed: every mode (subway, bus, commuter
            rail, ferry) and every effect (incl. elevator closures and
            notices); silver keeps rail and service-affecting alerts, and
            bronze stays complete (decision 0011)
Writes to:  bronze.mbta_alerts (append) — one row per alert per run: the
            alert's full JSON exactly as the API returned it

The API shows only alerts that are active or upcoming, and drops each one
within minutes of it ending. These snapshots are the project's own record of
past alerts (the MBTA's LAMP archive keeps only a version per change;
docs/roadmap.md), and silver uses them to tell when each alert ended (README,
"Alert end times").

Each alert is stored whole, from the whole feed, so new questions never depend
on what this script happened to keep; silver filters to rail and splits alerts
by route (mbta_alerts__by_route). Until 2026-10-24 this job wrote chosen
columns to what is now bronze.mbta_alerts_legacy, kept frozen as history
(decision 0002).
"""

# Import standard libraries
import json
import logging

# Import third party libraries
import pandas as pd

# Import shared ingest helpers
from common.fetch import fetch
from common.load import append_to_bronze
from common.mbta_api import API_URL, api_headers

# ── Fetch ─────────────────────────────────────────────────────────────────────

# The whole feed: no route filter, and every activity. Without filter[activity]
# the API documents a default of BOARD/EXIT/RIDE, which would drop alerts that
# only affect escalators, elevators, parking, or bikes (a route filter does
# apply it); ALL is the documented way to get everything.
params = {'filter[activity]': 'ALL'}

alerts = fetch(f'{API_URL}/alerts', params=params, headers=api_headers(), timeout=30).json()['data']
logging.info(f'Fetched {len(alerts)} alerts')

# ── Shape ─────────────────────────────────────────────────────────────────────

# One row per alert: its ID, and the whole alert as compact JSON (key order kept)
rows = [{'alert_id': alert.get('id'), 'alert_json': json.dumps(alert, separators=(',', ':'))}
        for alert in alerts]

# ── Load ──────────────────────────────────────────────────────────────────────

append_to_bronze(pd.DataFrame(rows))
