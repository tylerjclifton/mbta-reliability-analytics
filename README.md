# MBTA Reliability Analytics

A full-stack data engineering project tracking MBTA rail reliability, ridership, and weather across the Red, Orange, Blue, and Green Lines.

**Live dashboard:** [tylerclifton.com](https://tylerclifton.com)

---

## What It Does

Ingests data from four sources on an automated schedule, transforms it through a medallion architecture, and serves a live analytics dashboard.

| Source | Data | Schedule |
|---|---|---|
| MBTA Alerts API | Service alerts (delays, suspensions, closures) | 4× daily — 12AM, 6AM, 12PM, 6PM ET |
| MBTA Routes API | Route metadata (names, types, colors) | Quarterly — Jan/Apr/Jul/Oct 1 at 12AM ET |
| NWS Weather API | Observations at Boston Logan Airport | 4× daily — 12AM, 6AM, 12PM, 6PM ET |
| MBTA ArcGIS Open Data | Gated station entries by route | Quarterly — Jan/Apr/Jul/Oct 1 at 12AM ET |

---

## Architecture

```
MBTA Alerts API  ──┐
MBTA Routes API  ──┤                        ┌─────────────────────────────────────────┐
NWS Weather API  ──┼──► Cloud Run Jobs ──►  │  BigQuery                               │──► Streamlit
MBTA Ridership   ──┘         ↑              │  stage → bronze → silver → gold         │
                      Cloud Scheduler       │              ↑ dbt Core                 │
                                            └─────────────────────────────────────────┘
```

**Medallion Layers**

| Layer | Role |
|---|---|
| `stage` | Raw API output written by ingest jobs |
| `bronze` | Typed, schema-enforced tables per source |
| `silver` | Cleaned, computed fields (duration, human-readable labels) |
| `gold` | Views — cross-source joins served directly to the dashboard |

---

## Stack

| Category | Technology |
|---|---|
| Cloud | GCP (BigQuery, Cloud Run, Cloud Scheduler, Artifact Registry) |
| Infrastructure | Terraform |
| Transformation | dbt Core |
| Dashboard | Streamlit |
| Containerization | Docker |
| Languages | Python, SQL (Jinja) |

---

## Dashboard

**Alerts Section**
- Active and past alerts with cause, effect, duration, and route
- Alerts by route and by month (last 12 months)
- Cause share and effect share (donut charts)
- Causes and effects broken out by route (normalized %)
- Cause → effect heatmap

**Ridership Section**
- Daily ridership vs active alert count (dual-axis, by line)
- Average ridership by day of week
- Temperature vs ridership and precipitation vs ridership (scatter with trendlines)

---

## Project Structure

```
infra/              Terraform — all GCP infrastructure
ingest/
  mbta-alerts/      MBTA service alert ingestion
  mbta-routes/      MBTA route metadata ingestion
  mbta-ridership/   ArcGIS gated entries ingestion (quarterly)
  nws-weather/      NWS Boston Logan weather ingestion
transform/          dbt Core project (models, macros, configs)
serve/              Streamlit dashboard
```
