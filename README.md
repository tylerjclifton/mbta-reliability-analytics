# MBTA Reliability Analytics

A full-stack data engineering project tracking MBTA rail reliability, ridership, and weather across the Red, Orange, Blue, and Green Lines.

**Live dashboard:** [tylerclifton.com](https://tylerclifton.com)

---

## What It Does

Ingests data from four sources on an automated schedule, transforms it through a medallion architecture, and serves a live analytics dashboard.

| Source | Data | Schedule | Each run pulls |
|---|---|---|---|
| MBTA Alerts API | Service alerts (delays, suspensions, closures) | Hourly | Current live feed (snapshot) |
| MBTA Routes API | Route metadata (names, types, colors) | Yearly — Jan 1 | Full route list (snapshot) |
| NOAA GHCN-Daily | Daily temperature, precipitation, snowfall at Boston Logan | Daily — 6AM ET | Last 10 days (NOAA revises recent days) |
| MBTA ArcGIS Open Data | Gated station entries by line | Weekly — Mondays 6AM ET | Full published history (catches revisions) |

The dbt transform runs hourly at :30.

---

## Architecture

```
MBTA Alerts API  ──┐
MBTA Routes API  ──┤                        ┌─────────────────────────────────────────┐
NOAA GHCN-Daily  ──┼──► Cloud Run Jobs ──►  │  BigQuery                               │──► Streamlit
MBTA Ridership   ──┘         ↑              │  bronze → silver → gold                 │
                      Cloud Scheduler       │            └─ dbt Core ─┘               │
                                            └─────────────────────────────────────────┘
```

### Medallion layers

Each layer is its own BigQuery dataset.

| Layer | Stored as | Written by | Role |
|---|---|---|---|
| `bronze` | Append-only tables (Terraform-managed, deletion-protected) | Ingest jobs | Raw history. Each run appends a new version of every record it saw; rows are never updated or deleted, so nothing depends on a source keeping its own history |
| `silver` | Views | dbt | Latest version of each record per source, cleaned and typed (alert start/end resolution, unit conversion, QC filtering) |
| `gold` | Tables, rebuilt hourly | dbt | Cross-source joins served to the dashboard |

| Bronze / silver table | Grain (silver) | How bronze grows |
|---|---|---|
| `mbta_alerts` | alert × route | Hourly snapshot of the live feed — the only record of alerts once they end |
| `mbta_routes` | route | Yearly snapshot |
| `mbta_ridership` | service date × line | Full history re-pulled weekly; silver keeps the latest value, so MBTA revisions win |
| `noaa_weather` | observation date | Last 10 days re-pulled daily; silver keeps the latest value |

| Gold table | Grain | Contents |
|---|---|---|
| `rail_alerts` | alert × route | Alerts with route name, line, and type |
| `rail_ridership` | service date × line | Gated entries, active alert count, and weather |

### Data quality

The transform job runs `dbt build` then `dbt source freshness`:

- **Grain tests** — every silver view and gold table is unique on its key
- **Join tests** — line names are one of the four rail lines; every alert's route exists in routes
- **Range tests** — temperatures, precipitation, gated entries, and severities are physically plausible
- **Coverage** — warns if any ridership day has no weather
- **Freshness** — fails the run if an ingest job stops writing to bronze (thresholds per source in `transform/models/bronze/_bronze__sources.yml`)

A failing test skips everything downstream of it, so bad data never reaches gold.

---

## Conventions

| Thing | Convention | Example |
|---|---|---|
| Datasets | Medallion layer | `bronze`, `silver`, `gold` |
| Bronze / silver tables | `<source>_<entity>`, same name in both layers | `mbta_alerts` |
| Gold tables | `<domain>_<entity>` | `rail_ridership` |
| Ingest jobs | `ingest/<source>-<entity>/main.py` → `bronze.<source>_<entity>` | `ingest/noaa-weather` → `bronze.noaa_weather` |
| Bronze columns | Source system's names, plus audit columns | `route_or_line`, `tmax` |
| Silver / gold columns | `snake_case`; keys `<entity>_id`; `_at` = TIMESTAMP (UTC); `_date` = DATE (Eastern); measures carry their unit; booleans `is_` | `alert_start_at`, `precipitation_in`, `is_in_feed` |
| Audit columns | On every bronze/silver table | `ingested_at`, `ingested_by` |
| dbt models | Header comment (purpose, grain, numbered steps); CTEs named after the step | `latest_versions`, `quality_checked` |
| Ingest scripts | Docstring (source, cadence, each run, writes to); Fetch → Shape → Write sections | |

---

## Stack

| Category | Technology |
|---|---|
| Cloud | GCP (BigQuery, Cloud Run, Cloud Scheduler, Artifact Registry) |
| Infrastructure | Terraform (state in GCS: `mbta-reliability-analytics-tfstate`) |
| Transformation | dbt Core |
| Dashboard | Streamlit |
| Containerization | Docker |
| Languages | Python, SQL (Jinja) |

---

## Dashboard

**Alerts Section**
- Active and upcoming alerts with cause, effect, duration, and route
- Alerts by route and by month (last 12 months)
- Cause share and effect share (donut charts)
- Average duration by cause and effect
- Causes and effects broken out by route (normalized %)
- Cause → effect heatmap

**Ridership Section**
- Monthly ridership vs active alert count (dual-axis, by line)
- Average ridership by day of week
- Temperature, precipitation, and snowfall vs ridership (scatter with trendlines)

---

## Project Structure

```
infra/                  Terraform — all GCP infrastructure
  bigquery.tf           Datasets + bronze table schemas (single source of truth)
  cloud-run-jobs.tf     Ingest jobs (one per source) + transform job, image versions
  cloud-scheduler.tf    Cron triggers
ingest/                 One shared image for every ingest job
  common/bronze.py      Shared fetch + append-to-bronze helpers
  mbta-alerts/          MBTA service alert snapshots (hourly)
  mbta-routes/          MBTA route metadata snapshots (yearly)
  mbta-ridership/       ArcGIS gated entries, full history (weekly)
  noaa-weather/         NOAA GHCN-Daily for Boston Logan (daily)
transform/              dbt Core project
  models/bronze/        Source declarations + freshness thresholds
  models/silver/        Per-source views + tests
  models/gold/          Dashboard tables + tests
  macros/               keep_latest_version, null_if_failed_ghcn_qc
  tests/generic/        unique_combination, accepted_range
serve/                  Streamlit dashboard
scripts/build-image.sh  Build + push any component's image
```

---

## Development & Deployment

```bash
# Local environment (all components + dev tools)
pip install -r requirements.txt

# Run an ingest job locally (writes to the real bronze table)
PYTHONPATH=ingest python ingest/noaa-weather/main.py

# Build/test dbt models locally (uses gcloud application-default credentials)
cd transform && dbt build --profiles-dir . --target local

# Ship a change: build + push the image, bump its tag in Terraform, apply
scripts/build-image.sh ingest v1.0.1      # or transform / serve
#   → edit local.ingest_image_tag in infra/cloud-run-jobs.tf
cd infra && terraform apply

# Backfill weather (e.g. ~2 years)
gcloud run jobs execute ingest-noaa-weather --region=us-east1 --update-env-vars LOOKBACK_DAYS=800
```
