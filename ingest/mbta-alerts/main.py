"""
Ingest: MBTA service alerts

Source:     MBTA V3 API /alerts (https://api-v3.mbta.com)
Cadence:    Every 15 minutes
Each run:   Snapshots every rail alert currently in the live feed, including
            ones that don't affect train service (e.g. elevator closures,
            notices) — silver filters those out, so bronze stays complete
Writes to:  bronze.mbta_alerts (append) — one row per alert × route per run

The API only shows alerts that are active or upcoming; once an alert ends it
disappears for good. Bronze's snapshots are therefore the only record of past
alerts, and silver uses the last run an alert was seen in to tell when it ended
(whichever comes first: that, or the end time the MBTA posted).
"""

# Import standard libraries
import datetime
import logging
import os

# Import third party libraries
import pandas

# Import shared ingest helpers
from common.bronze import append_to_bronze, fetch

# Rail routes to snapshot — Silver Line, Mattapan, buses, and ferries excluded
TARGET_ROUTES = ['Red', 'Blue', 'Orange', 'Green-B', 'Green-C', 'Green-D', 'Green-E']


def parse_timestamp(value):
    """Parse an ISO-8601 string from the API; None when missing or malformed."""
    try:
        return datetime.datetime.fromisoformat(value) if value else None
    except (ValueError, TypeError):
        return None


# ── Fetch ─────────────────────────────────────────────────────────────────────

# Filter to target routes server-side; the API key is optional but removes the
# anonymous rate limit
params = {'filter[route]': ','.join(TARGET_ROUTES)}
if os.getenv('MBTA_API_KEY'):
    params['api_key'] = os.getenv('MBTA_API_KEY')

alerts = fetch('https://api-v3.mbta.com/alerts', params=params, timeout=30).json()['data']

# ── Shape ─────────────────────────────────────────────────────────────────────

rows = []
for alert in alerts:
    attributes = alert.get('attributes', {})

    # Use the first active period; later periods (e.g. recurring weekend
    # closures) aren't tracked
    period = (attributes.get('active_period') or [{}])[0]

    # One row per targeted route the alert applies to
    alert_routes = {entity.get('route') for entity in attributes.get('informed_entity', [])}
    for route in sorted(alert_routes & set(TARGET_ROUTES)):
        rows.append({
            'alert_id':            alert.get('id'),
            'route':               route,
            'active_period_start': parse_timestamp(period.get('start')),
            'active_period_end':   parse_timestamp(period.get('end')),
            'duration_certainty':  attributes.get('duration_certainty'),
            'header':              attributes.get('header'),
            'description':         attributes.get('description'),
            'cause':               attributes.get('cause'),
            'effect':              attributes.get('effect'),
            'severity':            attributes.get('severity'),
            'created_at':          parse_timestamp(attributes.get('created_at')),
            'updated_at':          parse_timestamp(attributes.get('updated_at')),
        })

logging.info(f"{len(alerts)} alerts in feed, {len(rows)} rail alert × route rows")

# ── Write ─────────────────────────────────────────────────────────────────────

append_to_bronze(pandas.DataFrame(rows))
