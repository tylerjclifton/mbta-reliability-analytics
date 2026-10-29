# Roadmap

Planned work, roughly in order, with why. Move an item to a [decision record](decisions/) once it's decided, and delete it once it's done.

## Later

- **MBTA estimate accuracy model** (~January 2027). Are the MBTA's posted end times any good, and can a model beat them? This needs months of 15-minute snapshots (they began 2026-10-21). Early sign, from only 5 alerts: estimates sit ~2 hours out while delays clear in ~30 minutes.
- **Riders affected per incident.** The ridership source is per station, but the ingest sums it per line. Station-level entries × stations affected would weight incidents by the riders they hit.
- **Map line geometry.** Draw the lines themselves (MBTA shapes API) behind the station dots.

## Dated upkeep

| When | What |
|---|---|
| Before **2027-07-15** | Upgrade dbt (1.12 support ends); consider v2 ([0009](decisions/0009-runtime-versions.md)) |
| Before **2027-08-03** | tylerclifton.com renews; confirm auto-renew ([setup](setup.md#things-that-live-outside-the-repo)) |
| ~2029-10 | Python 3.13 support ends |
| ~2030 (mid) | A full rebuild of the alert tables exceeds the 50 GiB per-query limit (bronze alerts grow ~15 GB/year). Hourly runs are unaffected; before any `--full-refresh`, raise `maximum_bytes_billed` in `transform/profiles.yml` ([0011](decisions/0011-capture-every-mode.md)) |
