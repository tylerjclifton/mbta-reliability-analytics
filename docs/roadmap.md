# Roadmap

Planned work, roughly in order, with why. Move an item to a [decision record](decisions/) once it's decided, and delete it once it's done.

## Later

- **MBTA estimate accuracy model.** Are the MBTA's posted end times any good, and can a model beat them? Measured 2026-11-09 on 9,060 subway delays since 2019-09: the first posted end sits a median 120 minutes out while delays clear in 36. Its typical error is 87 minutes, 4% within 15 minutes of the real end, against 17 minutes and 44% for the median duration of the delay's cause. The dashboard's "Posted end times" card shows the MBTA's side over the trailing 12 months (`gold.rail_delay_estimates`); the cause's median beside it needs no model either. LAMP keeps every version's posted end and the close time back to 2019; the 15-minute snapshots add finer detail on when estimates change.
- **Riders affected per incident.** The ridership source is per station, but the ingest sums it per line. Station-level entries × stations affected would weight incidents by the riders they hit. The MBTA's seasonal rail ridership by hour and stop (Fall 2024 and Fall 2025 on its open data portal) gives station × hour weights, which would also turn out-of-service hours into station-hours.
- **Commuter rail delay causes.** Trains on time and canceled, by line, load weekly from 2016 on ([0019](decisions/0019-reliability-riders-feel.md)); what's left is why trains run late. LAMP holds ~134k commuter rail "Train N … X minutes behind schedule" alerts since 2019, and their text often names a cause, though the cause field is almost always "unknown". Alerts cover only trains the MBTA posted about. Actual times for every train would mean capturing vehicle positions, which exist only in the live API (LAMP's rail data is subway only). That's undecided; if done, use a small Cloud Run service polled every 1–2 minutes (~$0–3/month), not a job every minute (~$140/year, from execution times measured 2026-11-01).
- **Subway train performance.** LAMP publishes actual arrival, departure, travel, dwell, and headway times per trip × stop since September 2019, computed from the same vehicle feeds the API serves (`/vehicles`). The MBTA's excess trip time already summarizes them for Red, Orange, and Blue, weighted by riders ([0019](decisions/0019-reliability-riders-feel.md)); these files would add the Green Line and each trip's detail, but it's data the project doesn't take through the API today, so it's set aside (see the rule under [LAMP](#the-mbtas-lamp-archive)). If taken up: one file per service date (~1.8 MB) plus an `index.csv` of last-modified times, and LAMP regenerates old days (every file was rewritten 2026-10-22), so a daily job pulls new and changed days. About 13M rows a year, so silver and gold must be incremental, partitioned by service date: an hourly transform rescanning the whole table would cost ~$20–100+/month, with no single query tripping the per-query limit.
- **More of the MBTA's open data.** Checked 2026-11-14, each small unless noted:
  - **The RIDE Ridership and Reliability:** daily trips requested, completed, on time, and missed, from 2025-09; two retired datasets may reach further back.
  - **Rapid Transit and Bus Prediction Accuracy:** the weekly share of countdown predictions that were right, subway and bus, from 2020-08. It belongs beside the dashboard's posted end times: can riders trust what the MBTA tells them?
  - **Bus Arrival Departure Times:** every bus timepoint, ~400 MB a year. Reliability for the second-biggest mode, but the ingest would need to summarize it.
  - **2025 System-Wide Passenger Survey:** who rides each line (income, car access, and more), one snapshot.
  - **Outside the portal:** the MBTA's archive of past GTFS schedules (how much service ran, as through the 2022 subway cuts), and Red Sox, Celtics, and Bruins home games (station spikes).

## The MBTA's LAMP archive

LAMP (Lightweight Application for Measuring Performance, [github.com/mbta/lamp](https://github.com/mbta/lamp)) is the MBTA's own pipeline that turns its live feeds into history, published at [performancedata.mbta.com](https://performancedata.mbta.com/) (field definitions in its `Data_Dictionary.md`). Checked 2026-11-01:

| Dataset | Contents | Coverage |
|---|---|---|
| Alerts (`LAMP_RT_ALERTS`) | Every alert, every mode: text, cause, effect, routes and stops, posted active periods, close time; one row per informed entity × active period × version | September 2019 on, rewritten about hourly; 411k alerts |
| Subway performance (`subway-on-time-performance-v1`, and `LAMP_ALL_RT_fields` for all dates in one file) | Actual vs scheduled times per trip × stop | September 2019 on; subway and Mattapan only, no commuter rail |
| Bus events (`LAMP_ALL_Bus_Events`, not listed on the site) | Actual vs scheduled times per trip × stop | Bus only; a rolling window, not history (2025-12-19 to 2026-11-03 on 2026-11-03, ~110M rows) |
| GTFS archive | Every schedule issued | 2009 on |

Against bronze, 2026-10-29 to 11-01: LAMP held all 997 alerts bronze saw, and of the 853 created in that window, bronze missed 8 (7 open under 2 minutes, none subway). LAMP is one file per dataset, rewritten in place, so it's a backfill source, not a replacement: the alerts job keeps its own capture ([0001](decisions/0001-append-only-bronze.md)).

**The rule:** take from LAMP only data the project already takes through the API, which today means alerts. It fills history; it doesn't add new kinds of data.

## Dated upkeep

| When | What |
|---|---|
| Before **2027-07-15** | Upgrade dbt (1.12 support ends); consider v2 ([0009](decisions/0009-runtime-versions.md)) |
| Before **2027-08-03** | tylerclifton.com renews; confirm auto-renew ([setup](setup.md#things-that-live-outside-the-repo)) |
| ~2029-10 | Python 3.13 support ends |
| ~2030 (mid) | A full rebuild of the alert tables exceeds the 50 GiB per-query limit (estimate and growth rate in [0011](decisions/0011-capture-every-mode.md)). Hourly runs are unaffected; before any `--full-refresh`, raise `maximum_bytes_billed` in `transform/profiles.yml` |
| ~2030 (mid) | A full rebuild of `silver.mbta_ferry_trips__base` writes one partition per service day, past BigQuery's 4,000 per job (2,493 days through March 2026). Weekly runs replace about a year of days and are unaffected; before any `--full-refresh`, partition it by month, reading whole months from bronze so a partial month isn't overwritten |
