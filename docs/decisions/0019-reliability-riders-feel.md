# 0019 — Reliability as riders feel it: subway trip times, commuter rail on time, and the rider survey

**Status:** Accepted · **Date:** 2026-11-14

## Context
The project measures reliability through alerts: what the MBTA posts, when, and for how long ([0016](0016-alerts-before-capture-from-lamp.md)). Alerts miss what the MBTA doesn't post. Slow zones, for one, cost Red Line riders minutes on every trip in 2023 but rarely appeared as alerts: 11 of that year's 884 Red, Orange, and Blue Line incidents mentioned a speed restriction (checked 2026-11-14). Commuter rail had riders but no reliability measure ([0018](0018-ridership-for-every-mode.md)), and nothing said how riders themselves judge the service. The MBTA's open data portal publishes all three, checked 2026-11-14:

| Dataset | Grain | Coverage |
|---|---|---|
| Heavy Rail Excess Trip Time | service date × half hour × line × direction: estimated riders, and their trip time (wait plus travel) against a baseline | 2022-01-01 on, Red, Orange, and Blue (Green "in the future"); replaced about weekly, weeks late (through 2026-09-30) |
| Commuter Rail Reliability | service date × line × peak or off-peak: trains measured, on time, and canceled | 2016-01-01 on; replaced about weekly (through 2026-10-31) |
| Service Customer Satisfaction | monthly survey × question: respondents and the share giving each of seven answers | 2016-02 on, four questions (one added 2017-07), ~500 respondents a month |

Commuter rail reliability rows aren't unique: a line's branches are published as separate rows, sometimes under one name (in 2016, two "Newburyport/Rockport Line" rows a day, the Newburyport and Rockport branches). The MBTA publishes numerators and denominators separately so they can be summed before dividing.

Options rejected:
- **The per-train subway files** (Rapid Transit Travel Times, Headways, Events): ~13M rows a year, set aside on the [roadmap](../roadmap.md). Excess trip time is the MBTA's own summary of them, weighted by riders.
- **Ferry Reliability:** the project's on-time share, from every trip leg, already matches it within about a point ([0018](0018-ridership-for-every-mode.md)).
- **Commuter rail lateness from alert text** (the roadmap's earlier plan): alerts cover only trains the MBTA posted about, while the reliability file counts every train.
- **The RIDE's reliability, prediction accuracy, and bus arrival and departure times:** worth having, but each is a smaller gap or a bigger job; they're on the roadmap.

## Decision
- Three weekly ingest jobs, each writing its own bronze table, values as published:
  - `ingest-mbta-excess-trip-time` downloads the whole file (~95 MB) and keeps the last 120 days of service (`LOOKBACK_DAYS`) in `bronze.mbta_excess_trip_time`.
  - `ingest-mbta-commuter-rail-reliability` does the same with its ~13 MB file, into `bronze.mbta_commuter_rail_reliability`.
  - `ingest-mbta-customer-satisfaction` pulls the whole survey file (~500 rows) into `bronze.mbta_customer_satisfaction`.
- Both files with a lookback were loaded whole once with `LOOKBACK_DAYS=4000`.
- Silver keeps each day's rows from the latest load that covered it, as for ferry trips, since commuter rail rows have no key to match on.
- Each chart takes one of these sources, never two mixed (one source per view, as in [0018](0018-ridership-for-every-mode.md)).

## Consequences
- The subway has a reliability measure riders feel, weighted by how many rode, that alerts can't give: extra minutes per trip, slow zones included. It's an estimate from the MBTA's model, and only for the Red, Orange, and Blue Lines.
- Commuter rail has its punctuality, by line, back to 2016.
- The dashboard can set what riders say beside what the measures show.
- Bronze grows by about 1 million rows a year from excess trip time (~18,000 rows a run × 52), 200,000 from commuter rail reliability, and 26,000 from the survey. Billed on compressed bytes, that costs cents ([0014](0014-bronze-physical-storage-billing.md)).
- A file the MBTA stops updating for 120 days fails its job, which alerts.

## History
- **2026-11-15:** the dashboard shows riders only for modes other than the subway, so its last section, "Riders on every mode", stays one subject; the subway sections above it carry reliability. The commuter rail trains-late card and the ferry's late shares came off. Commuter rail reliability keeps loading, ready for a commuter rail view, and `gold.ferry_performance` keeps its on-time share.
- **2026-11-16:** commuter rail trains late and the ferry's on-time share are back on the dashboard, in its last section, renamed "Every mode": riders on every mode, and punctuality wherever the MBTA publishes it for every trip ([0020](0020-collect-broadly-show-what-is-used.md)).
