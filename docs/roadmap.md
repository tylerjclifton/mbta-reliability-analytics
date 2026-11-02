# Roadmap

Planned work, roughly in order, with why. Move an item to a [decision record](decisions/) once it's decided, and delete it once it's done.

## Next

- **Subway train performance.** [LAMP](#the-mbtas-lamp-archive) publishes actual arrival, departure, travel, dwell, and headway times per trip × stop since September 2019. That measures reliability directly, not only through alerts, and rolls up to the dashboard's day × line grain. It's published as one file per service date (~1.8 MB) plus an `index.csv` listing each file's last-modified time, and LAMP regenerates old days (every file was rewritten 2026-10-22), so a daily job pulls new and changed days. Plan: bronze from 2019, since LAMP is the only public copy of 2019–2022 (about 2 GB compressed for the extra years); models and dashboard from 2023, after the Green Line Extension opened (every current station exists throughout) and covering the 2023 slow zones and their 2024 repair. About 13M rows a year: silver and gold must be incremental, partitioned by service date. An hourly transform that rescans the whole table would cost ~$20–100+/month, and no single query would trip the per-query limit.
- **Backfill alert history from LAMP.** LAMP's alerts archive would take incident history back to 2019 instead of mid-2026, fill the June 8 – July 1, 2026 gap, and add stations for alerts from before full-JSON capture ([0002](decisions/0002-raw-alert-capture.md)). It lands in a new bronze table, never in the existing ones ([0001](decisions/0001-append-only-bronze.md)). LAMP keeps a version only when an alert changes, not every 15 minutes, so backfilled alerts would end at LAMP's close time instead of when they left the feed: check the two agree on alerts both sources have before mixing them. The joins need weather and ridership back as far: NOAA keeps full history (the weather job's `LOOKBACK_DAYS` override), but the ridership layer starts 2024-10, so check whether the MBTA publishes earlier gated entries.

## Later

- **MBTA estimate accuracy model.** Are the MBTA's posted end times any good, and can a model beat them? Early sign, from only 5 alerts: estimates sit ~2 hours out while delays clear in ~30 minutes. LAMP keeps every version's posted end and the close time back to 2019, so this no longer has to wait for months of 15-minute snapshots (they began 2026-10-21); those snapshots add finer detail on when estimates change.
- **Riders affected per incident.** The ridership source is per station, but the ingest sums it per line. Station-level entries × stations affected would weight incidents by the riders they hit.
- **Map line geometry.** Draw the lines themselves (MBTA shapes API) behind the station dots.
- **Commuter rail lateness by line.** LAMP holds ~134k commuter rail "Train N … X minutes behind schedule" alerts since 2019, so how late trains run, by line, can be measured on years of history. The alert text often names a cause, though the cause field is almost always "unknown". Needs the GTFS schedule for a denominator (trains run). Alerts cover only trains the MBTA posted about. Actual times for every train would mean capturing vehicle positions, which exist only in the live API (LAMP's rail data is subway only). That's undecided; if done, use a small Cloud Run service polled every 1–2 minutes (~$0–3/month), not a job every minute (~$140/year, from execution times measured 2026-11-01).
- **Bus and ferry** stay unmodeled. A bus reliability project would pair bus alerts with LAMP's stop-level bus events (actual times per trip × stop). Ferry has no ridership or performance source yet, only weather (Logan reports wind).

## The MBTA's LAMP archive

LAMP (Lightweight Application for Measuring Performance, [github.com/mbta/lamp](https://github.com/mbta/lamp)) is the MBTA's own pipeline that turns its live feeds into history, published at [performancedata.mbta.com](https://performancedata.mbta.com/) (field definitions in its `Data_Dictionary.md`). Checked 2026-11-01:

| Dataset | Contents | Coverage |
|---|---|---|
| Alerts (`LAMP_RT_ALERTS`) | Every alert, every mode: text, cause, effect, routes and stops, posted active periods, close time; one row per informed entity × active period × version | September 2019 on, rewritten about hourly; 411k alerts |
| Subway performance (`subway-on-time-performance-v1`, and `LAMP_ALL_RT_fields` for all dates in one file) | Actual vs scheduled times per trip × stop | September 2019 on; subway and Mattapan only, no commuter rail |
| Bus events (`LAMP_ALL_Bus_Events`) | Actual vs scheduled times per trip × stop | Bus only |
| GTFS archive | Every schedule issued | 2009 on |

Against bronze, 2026-10-29 to 11-01: LAMP held all 997 alerts bronze saw, and of the 853 created in that window, bronze missed 8 (7 open under 2 minutes, none subway). LAMP is one file per dataset, rewritten in place, so it's a backfill source, not a replacement: the alerts job keeps its own capture ([0001](decisions/0001-append-only-bronze.md)).

## Dated upkeep

| When | What |
|---|---|
| Before **2027-07-15** | Upgrade dbt (1.12 support ends); consider v2 ([0009](decisions/0009-runtime-versions.md)) |
| Before **2027-08-03** | tylerclifton.com renews; confirm auto-renew ([setup](setup.md#things-that-live-outside-the-repo)) |
| Next ingest library upgrade | Add `pandas-gbq` to `ingest/requirements.txt` with any newer `google-cloud-bigquery`: newer versions will need it to load DataFrames (a deprecation warning since 2026-10). The current pins don't need it |
| ~2029-10 | Python 3.13 support ends |
| ~2030 (mid) | A full rebuild of the alert tables exceeds the 50 GiB per-query limit (estimate and growth rate in [0011](decisions/0011-capture-every-mode.md)). Hourly runs are unaffected; before any `--full-refresh`, raise `maximum_bytes_billed` in `transform/profiles.yml` |
