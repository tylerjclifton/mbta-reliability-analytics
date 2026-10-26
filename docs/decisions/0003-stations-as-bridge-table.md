# 0003 — Alert stations live in a bridge table, not a new alert grain

**Status:** Accepted · **Date:** 2026-10-24

## Context
Alerts list the stops they affect, mostly as platforms, per direction. One Green Line suspension lists 118 stops. Making the alert tables alert × route × stop would:
- multiply rows (repeating header and description text for every stop)
- leave older rows with no stop and newer ones with stops
- break every downstream model that assumes alert × route

## Decision
- Alerts keep their alert × route grain.
- Stations live in a separate bridge table, `silver.mbta_alerts__by_station` (alert × route × station). It's unpacked from the raw JSON, with platforms rolled up to their station through `silver.mbta_stops__base`.
- Gold joins or summarizes it: `rail_incidents.stations_affected` (same grain as before) and `rail_incident_stations` for the map.
- `stations_affected` distinguishes **NULL** (no raw data: before capture, unknown) from **0** (captured, but the alert names no station, as with most line-wide delays).

## Consequences
- Nothing existing changed grain or broke.
- Platforms are kept in bronze but modeled at the station level. Direction is kept as "both" or the one direction's terminal.
- Most delays are line-wide and never appear on the map. Shuttles, suspensions, and closures do.
