# 0018 — Ridership for every mode from the MBTA's monthly figures; ferry trips with their times

**Status:** Accepted · **Date:** 2026-11-13

## Context
The dashboard's ridership is gated station entries on the four subway lines ([0015](0015-ridership-history-from-archive.md)). The MBTA also runs the Mattapan trolley, buses (the Silver Line among them), commuter rail, ferries, and The RIDE (paratransit). What its open data portal publishes for those, checked 2026-11-13:

| Dataset | Grain | Coverage |
|---|---|---|
| Monthly Ridership by Mode and Line | month × day type (weekday, Saturday, Sunday, total) × mode or line | 2018-07 on, every mode, updated monthly |
| Ferry Daily Ridership by Trip, Route, and Stop | trip leg, with riders on and off and the scheduled and actual departure and arrival | 2018-11 on, updated irregularly (through 2026-03-31 on 2026-11-13) |
| Commuter Rail Ridership by Service Date and Line | service date × line, estimates | Last updated 2026-07 |
| Bus Ridership by Trip, Season, Route, Line, and Stop | seasonal averages | No daily or monthly series |

The monthly figures are what the MBTA reports to the National Transit Database: unlinked trips, so a ride with a transfer counts twice, and subway riders count whether or not they pass a gate. Its subway numbers run higher than gated entries (in Sep 2026, the Blue Line's weekday average was 55,781 against ~36,000 entries) and don't compare with them. Some of its rows are subtotals of others: Heavy Rail is Red + Orange + Blue, Light Rail is Green + Mattapan, All Bus is Bus + Silver Line (plus private-carrier and trackless-trolley routes, both now zero), and the "Total" day type is the other three together.

Options rejected:
- **Daily bus and commuter rail ridership now.** Bus has no daily series at all. Commuter rail's daily estimates arrive months late and belong with its reliability, which the project doesn't measure yet ([roadmap](../roadmap.md)).
- **Folding the monthly figures into `rail_ridership`.** They count differently, so the subway would carry two numbers that disagree.

## Decision
- Two weekly ingest jobs:
  - `ingest-mbta-mode-ridership` pulls the whole monthly layer each run (~5,000 rows) into `bronze.mbta_mode_ridership`, so revised months are captured.
  - `ingest-mbta-ferry-trips` re-pulls the last year of service each run (`LOOKBACK_DAYS`, default 365) into `bronze.mbta_ferry_trips`, so months published late or revised are captured without re-reading all ~400,000 rows. The whole layer was loaded once with `LOOKBACK_DAYS=4000`.
- Bronze keeps both as published. The monthly subtotals stay, and silver keeps only the rows that don't overlap, so no rider is counted twice. The ferry's text values (actual times, rider counts, "NA" for missing, negative riders off) stay text, and silver types them.
- Gated entries remain the subway's daily ridership. Riders by mode is a separate, monthly view, labeled as unlinked trips.

## Consequences
- Ridership covers every mode the MBTA runs: subway daily (gated entries), every mode monthly, and ferries by trip.
- The ferry has a reliability measure, its departures and arrivals against schedule, beside the subway's alerts.
- Bronze grows by ~265,000 rows a year from the monthly layer and up to ~2.8 million from the ferry's re-pulled year (~53,000 trip legs a year of service × 52 runs). Billed on compressed bytes, that costs cents ([0014](0014-bronze-physical-storage-billing.md)). Silver must read only each period's latest load, not every load.
- Ferry data runs months behind; the dashboard says through when.
- Commuter rail daily ridership and lateness stay on the roadmap, to be taken up together.
