# MBTA Reliability Analytics

[![CI](https://github.com/tylerjclifton/mbta-reliability-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/tylerjclifton/mbta-reliability-analytics/actions/workflows/ci.yml)

A full-stack data engineering project tracking MBTA rail reliability, ridership, and weather across the Red, Orange, Blue, and Green Lines.

**Live dashboard:** [tylerclifton.com](https://tylerclifton.com)

---

## What It Does

Ingests data from four sources on an automated schedule, transforms it through a medallion architecture, and serves a live analytics dashboard.

| Source | Data | Schedule | Each run pulls |
|---|---|---|---|
| MBTA Alerts API | Service alerts (delays, suspensions, closures) | Every 15 minutes | Current live feed (snapshot) |
| MBTA Routes API | Route metadata (names, types, colors) | Yearly — Jan 1 | Full route list (snapshot) |
| NOAA GHCN-Daily | Daily temperature, precipitation, snowfall at Boston Logan | Daily — 6AM ET | Last 10 days (NOAA revises recent days) |
| MBTA ArcGIS Open Data | Gated station entries by line | Weekly — Mondays 6AM ET | Full published history (catches revisions) |

The dbt transform runs hourly at :35.

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

Everything is defined in Terraform and deployed by GitHub Actions on every push to `main`.

### Medallion layers

Each layer is its own BigQuery dataset.

| Layer | Stored as | Written by | Role |
|---|---|---|---|
| `bronze` | Append-only tables (Terraform-managed, deletion-protected) | Ingest jobs | Raw history. Each run appends a new version of every record it saw; rows are never updated or deleted, so nothing depends on a source keeping its own history |
| `silver` | Views (one incremental table, below) | dbt | Latest version of each record per source, cleaned and typed (alert start/end resolution, unit conversion, QC filtering) |
| `gold` | Tables, rebuilt hourly | dbt | Cross-source joins served to the dashboard |

| Bronze / silver table | Grain (silver) | How bronze grows |
|---|---|---|
| `mbta_alerts` | alert × route | 15-minute snapshot of the live feed — the only record of alerts once they end |
| `mbta_routes` | route | Yearly snapshot |
| `mbta_ridership` | service date × line | Full history re-pulled weekly; silver keeps the latest value, so MBTA revisions win |
| `noaa_weather` | observation date | Last 10 days re-pulled daily; silver keeps the latest value |

| Gold table | Grain | Contents |
|---|---|---|
| `rail_incidents` | incident × route | One row per real-world event — the MBTA's re-posted/follow-up alerts collapsed (dashboard reads this) |
| `rail_ridership` | service date × line | Gated entries, active incident count, the day's most severe alert effect, and weather |

**`silver.mbta_alert_latest` is a table, not a view.** Alert snapshots add ~1 GB/year to bronze, and a view would re-read all of it for every model and test that uses alerts (~9× per transform), outgrowing the free query tier within a year. The incremental table reads only snapshots added since the last run, so cost stays flat; `dbt build --full-refresh` rebuilds it from bronze.

**Alert end times.** An alert ends at whichever comes first: the end time the MBTA posted (an estimate, usually rounded to the hour) or when it left the feed (midway between the last 15-minute run that saw it and the next). Since July 2026, 82% of alerts left the feed before their posted end.

**Alerts → incidents.** The MBTA often posts several alerts for one event (an update, or "delays due to an earlier disabled train at JFK/UMass"). `silver.mbta_alerts` groups them: same route, cause, effect, and station named in the header, starting within 2 hours of the previous alert's end (6 hours for "earlier"/"residual" follow-ups). Alerts that don't affect train service (notices, elevator/parking issues — `non_service_alert_effects` in `dbt_project.yml`) are excluded in silver; bronze keeps them.

### Data quality

The transform job runs `dbt build` then `dbt source freshness`:

- **Grain tests** — every silver view and gold table is unique on its key
- **Join tests** — line names are one of the four rail lines; every alert's route exists in routes
- **Range tests** — temperatures, precipitation, gated entries, and severities are physically plausible
- **Coverage** — warns if any ridership day has no weather
- **Incidents** — every incident has at least one alert and a start time
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

## Security & Access

Each workload runs as its own service account with access granted per dataset (`infra/iam.tf`). No workload has a project-wide data or admin role.

| Service account | Runs | Access |
|---|---|---|
| `ingest-jobs` | Ingest jobs | Write `bronze`; read the `mbta-api-key` secret |
| `dbt-bigquery` | Transform job | Read `bronze`; write `silver` and `gold` |
| `serve-bigquery` | Dashboard | Read `gold` |
| `job-scheduler` | Cloud Scheduler | Start the five Cloud Run jobs (`run.invoker` on each job) |
| `github-deployer` | CI/CD (GitHub Actions) | Build, push, and `terraform apply` — broad by necessity, usable only from this repo's `main` branch |

The three data workloads also hold `bigquery.jobUser` (permission to run queries), which grants no data access on its own. The MBTA API key lives in Secret Manager (`infra/secrets.tf`; Terraform owns the secret, the value is added by hand). Only the APIs the pipeline uses are enabled (`infra/apis.tf`), and Artifact Registry keeps the 5 newest versions of each image.

### Cost

The pipeline runs within GCP's free tiers. Query volume is dominated by BigQuery's 10 MB-per-query billing minimum (about 0.4 TiB/month of the free 1 TiB), not by data size, so it stays flat as history grows. A **$5/month budget** on the billing account emails at 50%, 90%, and 100% of actual spend and when spend is forecast to pass $5 (created with `gcloud billing budgets`, outside Terraform, since the CI deployer has no billing access).

---

## Stack

| Category | Technology |
|---|---|
| Cloud | GCP (BigQuery, Cloud Run, Cloud Scheduler, Artifact Registry, Secret Manager) |
| Infrastructure | Terraform (state in GCS: `mbta-reliability-analytics-tfstate`) |
| Transformation | dbt Core 1.12 (supported through July 2027) |
| Dashboard | Streamlit |
| CI/CD | GitHub Actions, Workload Identity Federation (keyless) |
| Containerization | Docker |
| Languages | Python 3.13 (supported through October 2029), SQL (Jinja) |

---

## Dashboard

Dark theme; official MBTA line colors for every line-level visual, a neutral violet for everything else. Every line-colored mark also carries a text label.

**Service status** — KPIs (active now, planned in 30 days, last 30 days vs prior, median duration); incidents happening now and planned work coming up, one card per incident

**Incident patterns** — incidents per week, by line, by cause and effect, median duration by cause, cause mix by line (heatmap)

**Ridership** — per-line average entries per day with year-over-year change; 24-month trend; ridership by alert effect (delay, suspension, shuttle) vs calm days; day of week

**Weather** — ridership on rainy, snowy, and unusually cold/warm days vs normal-weather days

Ridership figures are **average entries per day**, weekends included. Time windows: every section covers the trailing 12 months, except the ridership trend (24 months, for year-over-year) and weather (all history — storms are rare).

Incident history counts from when alert coverage became continuous (detected as the first incident after the last 14-day gap — the pre-October pipeline missed June 8 – July 1, 2026), so missing data never reads as a quiet day.

The alert-effect and weather charts use **% vs typical**: a day's entries vs the median for the same line, day of week, and month (federal holidays excluded), so line size, weekends, and seasons don't skew them.

---

## Project Structure

```
infra/                  Terraform — all GCP infrastructure
  bigquery.tf           Datasets (incl. dev sandboxes) + bronze table schemas (single source of truth)
  cloud-run-jobs.tf     Ingest jobs (one per source) + transform job
  cloud-run-services.tf Dashboard service + tylerclifton.com domain mapping
  cloud-scheduler.tf    Cron triggers
  iam.tf                Per-workload access (service-accounts.tf defines the accounts)
  deploy.tf             GitHub Actions deploy identity (Workload Identity Federation)
  secrets.tf            MBTA API key secret
  apis.tf               Enabled Google APIs
  artifact-registry.tf  Image repositories + cleanup policy
  cloud-storage.tf      Terraform state bucket
ingest/                 One shared image for every ingest job
  common/bronze.py      Shared fetch + append-to-bronze helpers
  tests/                Job tests against canned API responses
  mbta-alerts/          MBTA service alert snapshots (every 15 minutes)
  mbta-routes/          MBTA route metadata snapshots (yearly)
  mbta-ridership/       ArcGIS gated entries, full history (weekly)
  noaa-weather/         NOAA GHCN-Daily for Boston Logan (daily)
transform/              dbt Core project
  models/bronze/        Source declarations + freshness thresholds
  models/silver/        Per-source views + tests
  models/gold/          Dashboard tables (rail_incidents, rail_ridership) + tests
  macros/               keep_latest_version, null_if_failed_ghcn_qc
  tests/generic/        unique_combination, accepted_range
serve/                  Streamlit dashboard (app.py; pure helpers in helpers.py, tested in tests/)
scripts/build-image.sh  Build + push a component's image (used by CI/CD)
.github/workflows/      CI/CD: lint, tests, dbt parse, terraform validate; deploy on main
pyproject.toml          pytest + ruff config
```

---

## Development & Deployment

CI (`.github/workflows/ci.yml`) runs on every push and pull request without cloud credentials: ruff + pytest for the Python, `dbt parse` + sqlfluff for the SQL, and `terraform fmt` + `validate` for the infrastructure.

```bash
# Local environment (all components + dev tools)
pip install -r requirements.txt

# The same checks CI runs
ruff check ingest serve && pytest                                      # Python
(cd transform && dbt parse --profiles-dir . && sqlfluff lint models)   # SQL
(cd infra && terraform fmt -check -recursive && terraform validate)    # Terraform

# Run an ingest job locally (writes to the real bronze table)
PYTHONPATH=ingest python ingest/noaa-weather/main.py

# Build/test dbt models locally (uses gcloud application-default credentials).
# The local target writes to dev_silver / dev_gold — never the live datasets.
cd transform && dbt build --profiles-dir . --target local

# Preview the dashboard against dev_gold in the production image
docker build -t serve:dev serve && docker run --rm -p 8601:8080 \
  -v ~/.config/gcloud:/root/.config/gcloud:ro -e GOOGLE_CLOUD_PROJECT=mbta-reliability-analytics \
  -e GOLD_DATASET=dev_gold serve:dev          # → http://localhost:8601

# Ship a change: merge to main — CI/CD builds, pushes, applies, and runs the
# transform (see Continuous deployment below). To preview infra changes locally,
# plan against the deployed tag:
cd infra && terraform plan -var image_tag=$(git rev-parse --short=12 origin/main)

# Backfill weather (e.g. ~2 years)
gcloud run jobs execute ingest-noaa-weather --region=us-east1 --update-env-vars LOOKBACK_DAYS=800
```

### Continuous deployment

A push to `main` that passes CI deploys automatically (`deploy` job in `.github/workflows/ci.yml`):

1. Build the `ingest`, `transform`, and `serve` images and tag each with the commit (first 12 characters of the SHA)
2. `terraform apply -var image_tag=<commit>` — every job and the dashboard move to that commit's images
3. Run the transform once, so model changes are live immediately

GitHub authenticates to Google with **Workload Identity Federation** — a short-lived OIDC token exchanged for the `github-deployer` service account, so no keys exist anywhere. Only workflow runs on this repository's `main` branch are accepted (`infra/deploy.tf`). Rolling back is re-running the deploy for an earlier commit; Artifact Registry keeps the 5 most recent images.

The deploy identity can't create itself, so `infra/deploy.tf` was applied once from a workstation (`terraform apply -var image_tag=<deployed tag>`); every apply since runs in CI.

### Terraform state

State lives in the GCS bucket `mbta-reliability-analytics-tfstate` (versioned, 30-day history; `infra/cloud-storage.tf`), configured as the backend in `infra/main.tf`. The bucket is itself managed by Terraform, so it was bootstrapped once:

1. Comment out the `backend "gcs"` block in `infra/main.tf` and `terraform apply -target=google_storage_bucket.tfstate` (state is local).
2. Restore the block and run `terraform init -migrate-state` to move the local state into the bucket.

After that, `terraform init` in `infra/` is all a new machine needs (with `gcloud auth application-default login`).
