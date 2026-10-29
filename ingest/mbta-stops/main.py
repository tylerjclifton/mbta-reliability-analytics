"""
Ingest: MBTA rail stops (stations and what's inside them)

Source:     MBTA V3 API /stops (https://api-v3.mbta.com)
Cadence:    Weekly (stations rarely change; platforms occasionally do)
Each run:   For each rail route, snapshots its stations plus every child stop
            inside them — platforms, entrances, and walkway nodes — with every
            attribute the API returns
Writes to:  bronze.mbta_stops (append) — one row per stop × route per run

Alerts name the stops they affect mostly by platform ID (e.g. 70145, Boston
University Central toward Boston College). This table maps each of those to
its station (parent_station_id) and gives stations their coordinates, so silver
can say which stations an alert affects and the dashboard can map them.

route_id is the route whose stations were requested: a station appears once
per route serving it (Park Street under Red and each Green branch), and so do
its child stops — a child stop's route_id says which route's station it's in,
not which route stops at it.
"""

# Import standard libraries
import logging
import os

# Import third party libraries
import pandas

# Import shared ingest helpers
from common.bronze import append_to_bronze, fetch

# Rail routes to snapshot — must match rail_routes in silver/mbta_alerts__by_route.sql
TARGET_ROUTES = ['Red', 'Blue', 'Orange', 'Green-B', 'Green-C', 'Green-D', 'Green-E']


def stop_row(route_id, stop):
    """One bronze row: every attribute of a stop, plus its route and parent station."""
    attributes = stop.get('attributes', {})
    parent = ((stop.get('relationships') or {}).get('parent_station') or {}).get('data') or {}
    return {
        'route_id':            route_id,
        'stop_id':             stop.get('id'),
        'stop_name':           attributes.get('name'),
        'location_type':       attributes.get('location_type'),
        'parent_station_id':   parent.get('id'),
        'platform_name':       attributes.get('platform_name'),
        'platform_code':       attributes.get('platform_code'),
        'description':         attributes.get('description'),
        'latitude':            attributes.get('latitude'),
        'longitude':           attributes.get('longitude'),
        'municipality':        attributes.get('municipality'),
        'address':             attributes.get('address'),
        'on_street':           attributes.get('on_street'),
        'at_street':           attributes.get('at_street'),
        'vehicle_type':        attributes.get('vehicle_type'),
        'wheelchair_boarding': attributes.get('wheelchair_boarding'),
    }


# ── Fetch + Shape ─────────────────────────────────────────────────────────────

# The API key is optional but removes the anonymous rate limit
api_key = {'api_key': os.getenv('MBTA_API_KEY')} if os.getenv('MBTA_API_KEY') else {}

rows = []
for route_id in TARGET_ROUTES:
    # filter[route] returns the route's stations; include=child_stops adds
    # everything inside them (as JSON:API "included" resources)
    params = {'filter[route]': route_id, 'include': 'child_stops', **api_key}
    body = fetch('https://api-v3.mbta.com/stops', params=params, timeout=30).json()

    stations = body.get('data', [])
    children = body.get('included', [])
    rows += [stop_row(route_id, stop) for stop in stations + children]
    logging.info(f"{route_id}: {len(stations)} stations, {len(children)} child stops")

# ── Write ─────────────────────────────────────────────────────────────────────

df = pandas.DataFrame(rows)
# Nullable integers: a missing enum stays NULL instead of turning the column to float
for column in ['location_type', 'vehicle_type', 'wheelchair_boarding']:
    df[column] = df[column].astype('Int64')

append_to_bronze(df)
