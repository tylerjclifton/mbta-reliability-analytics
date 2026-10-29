# MBTA Reliability Analytics

[![CI](https://github.com/tylerjclifton/mbta-reliability-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/tylerjclifton/mbta-reliability-analytics/actions/workflows/ci.yml)

A full-stack data engineering project tracking MBTA rail reliability, ridership, and weather across the Red, Orange, Blue, and Green Lines.

**Live dashboard:** [tylerclifton.com](https://tylerclifton.com)

**Docs:** [setup on a new machine](docs/setup.md) · [runbook](docs/runbook.md) · [decision records](docs/decisions/README.md) · [roadmap](docs/roadmap.md)

---

## What It Does

Ingests data from five sources on an automated schedule, transforms it through a medallion architecture, and serves a live analytics dashboard.

| Source | Data | Schedule | Each run pulls |
|---|---|---|---|
| MBTA Alerts API | Service alerts (delays, suspensions, closures) | Every 15 minutes | Whole live feed, every mode (snapshot); the dashboard uses rail |
| MBTA Routes API | Route metadata (names, types, colors) | Yearly — Jan 1 | Full route list (snapshot) |
| MBTA Stops API | Stations and their platforms, with coordinates | Weekly — Mondays 6:30AM ET | Every rail station and the stops inside it (snapshot) |
| NOAA GHCN-Daily | Daily temperature, precipitation, snowfall at Boston Logan | Daily — 6AM ET | Last 10 days (NOAA revises recent days) |
| MBTA ArcGIS Open Data | Gated station entries by line | Weekly — Mondays 6AM ET | Full published history (catches revisions) |

The dbt transform runs hourly at :35.

---

## Architecture

```
MBTA Alerts API  ──┐
MBTA Routes API  ──┤
MBTA Stops API   ──┤                        ┌─────────────────────────────────────────┐
NOAA GHCN-Daily  ──┼──► Cloud Run Jobs ──►  │  BigQuery                               │──► Streamlit
MBTA ArcGIS      ──┘         ↑              │  bronze → silver → gold                 │
                      Cloud Scheduler       │            └─ dbt Core ─┘               │
                                            └─────────────────────────────────────────┘
```

Everything is defined in Terraform and deployed by GitHub Actions on every push to `main`.

### Medallion layers

Each layer is its own BigQuery dataset.

| Layer | Stored as | Written by | Role |
|---|---|---|---|
| `bronze` | Append-only tables (Terraform-managed, deletion-protected) | Ingest jobs | Raw history. Each run appends a new version of every record it saw; rows are never updated or deleted, so nothing depends on a source keeping its own history |
| `silver` | Views (two incremental tables, below) | dbt | Each source's **cleaned copy** (latest version, renamed and typed, unit conversion, QC filtering), plus steps that each do **one job** (split alerts by route or station, resolve start/end, group into incidents) |
| `gold` | Tables, rebuilt hourly | dbt | Cross-source joins served to the dashboard |

| Bronze table | Grain | How it grows |
|---|---|---|
| `mbta_alerts` | alert × ingest run | The live alerts table: a 15-minute snapshot of the whole feed (every mode since 2026-10-28), each alert's full JSON — the only record of alerts once they end |
| `mbta_alerts_legacy` | alert × route × ingest run | Frozen: the same snapshots as the old ingest shaped them, 2026-06-07 to 2026-10-24 (below). Never written, never deleted |
| `mbta_stops` | stop × route × ingest run | Weekly snapshot of every rail station and its platforms, entrances, and nodes |
| `mbta_routes` | route × ingest run | Yearly snapshot |
| `mbta_ridership` | service date × line × ingest run | Full published history re-pulled weekly |
| `noaa_weather` | observation date × ingest run | Last 10 days re-pulled daily (NOAA revises recent days) |

Silver models are named `<bronze table>__<step>`. `__base` is each source's cleaned copy, with no business rules; every other step does one job.

| Silver model | Grain | What it is |
|---|---|---|
| `mbta_alerts__base` | alert | Each alert's latest full JSON (incremental table) |
| `mbta_alerts__by_route` | alert × route | Each alert split into one row per rail route, with history from `mbta_alerts_legacy` before full-JSON capture began (incremental table) |
| `mbta_alerts__resolved` | alert × route | Service-affecting alerts with their real start and end, and whether they're still in the feed |
| `mbta_alerts__grouped` | alert × route | Each alert tagged with its incident, with readable labels and durations (gold reads this; `gold.rail_incidents` has one row per incident) |
| `mbta_alerts__by_station` | alert × route × station | Which stations each alert affects, and in which direction |
| `mbta_routes__base` | route | Each rail route and the line it belongs to |
| `mbta_stops__base` | stop × route | Every station and platform, mapped to its station, with coordinates |
| `mbta_ridership__base` | service date × line | The latest published entries, so MBTA revisions win |
| `noaa_weather__base` | observation date | Weather in °F and inches, failed quality checks removed, latest value |

| Gold table | Grain | Contents |
|---|---|---|
| `rail_incidents` | incident × route | One row per real-world event — the MBTA's re-posted/follow-up alerts collapsed (dashboard reads this), with how many stations it names |
| `rail_incident_stations` | incident × route × station | The stations each incident names, with coordinates and direction, for the map |
| `rail_stations` | station × line | Every rail station's coordinates, the map's backdrop |
| `rail_ridership` | service date × line | Gated entries, active incident count, the day's most severe alert effect, whether it was a calm day, and weather |

**`silver.mbta_alerts__by_route` and `silver.mbta_alerts__base` are tables, not views.** Everything else in silver is a view, recomputed every run ([0010](docs/decisions/0010-silver-naming-and-materialization.md)). Alert snapshots add ~15 GB/year to bronze (the whole feed, every mode), and a view would re-read all of it for every model and test that uses alerts (~9× per transform), outgrowing the free query tier within a year. The incremental tables read only snapshots added since the last run, so cost stays flat; `dbt build --full-refresh` rebuilds them from bronze.

**Full alert JSON.** Until 2026-10-24 the alerts job wrote only chosen fields to the table now named `bronze.mbta_alerts_legacy`, dropping the rest: the stops each alert affects, every active period after the first, and attributes like `lifecycle`. It now writes each alert's full JSON to `bronze.mbta_alerts` instead, and `silver.mbta_alerts__by_route` splits it into one row per route. Since 2026-10-28 that's the whole feed (no route filter, every activity): bus, commuter rail, and ferry alerts are kept in bronze for future use (~15 GB/year), while silver keeps only rail ([0011](docs/decisions/0011-capture-every-mode.md)). The old table is kept, frozen, as history: silver reads it for snapshots before full-JSON capture began (`alerts_raw_capture_start` in `dbt_project.yml`) and `bronze.mbta_alerts` from then on. Both were written in parallel for a day and matched row for row. Alerts that ended before full-JSON capture have no stop data, since the API never returns them again ([0002](docs/decisions/0002-raw-alert-capture.md)).

**Alerts → stations.** Alerts name the stops they affect, mostly by platform and direction. `silver.mbta_alerts__by_station` unpacks that list from each alert's full JSON and rolls platforms up to their station using `silver.mbta_stops__base`, one row per alert × route × station. It sits beside the alert × route models instead of changing their grain. Shuttles, suspensions, and station closures name their stations; most delays are line-wide and name none. `gold.rail_incidents.stations_affected` is NULL for incidents from before full-JSON capture began (unknown) and 0 for ones that named no stations.

**Alert end times.** An alert ends at whichever comes first: the end time the MBTA posted (an estimate, usually rounded to the hour) or when it left the feed (midway between the last 15-minute run that saw it and the next). Since July 2026, 82% of alerts left the feed before their posted end.

**Alerts → incidents.** The MBTA often posts several alerts for one event (an update, or "delays due to an earlier disabled train at JFK/UMass"). `silver.mbta_alerts__grouped` groups them: same route, cause, effect, and station named in the header, starting within 2 hours of the previous alert's end (6 hours for "earlier"/"residual" follow-ups). Alerts that don't affect train service (notices, elevator/parking issues — `non_service_alert_effects` in `dbt_project.yml`) are excluded in `silver.mbta_alerts__resolved`; bronze keeps them.

### Data quality

The transform job (`transform/run.py`) runs `dbt build` then `dbt source freshness`:

- **Grain tests** — every silver model and gold table is unique on its key
- **Join tests** — line names are one of the four rail lines; every alert's route exists in routes
- **Range tests** — temperatures, precipitation, gated entries, and severities are physically plausible
- **Coverage** — warns if any ridership day has no weather
- **Incidents** — every incident has at least one alert and a start time
- **Freshness** — fails the run if an ingest job stops writing to bronze (thresholds per source in `transform/models/bronze/_bronze__sources.yml`)

A failing test skips everything downstream of it, so bad data never reaches gold.

### Alerting

Failures email `alert_email` (`infra/variables.tf`) — never successful runs (`infra/monitoring.tf`):

- **`<job> failed`** — any job (ingest or transform) whose execution fails. The email carries the job's own error report: the exception and traceback for an ingest job; dbt's failure summary (failed tests, stale sources, or the error) for the transform. Ingest jobs retry once, and only the final attempt reports, so a blip the retry absorbs sends nothing. While a job keeps failing, at most one email every 6 hours.
- **`transform hasn't succeeded in 3 hours`** — backstop for failures a job can't report itself (timeout, out of memory, never started). An ingest job failing that way surfaces through the transform's freshness check.

The dashboard shows visitors the same thing: the dot beside "Alerts updated" is green while alerts are under 2 hours old, amber with "running behind" at 2–6 hours (hourly runs missed), and red with "may be out of date" beyond that (`serve/helpers.py`, `freshness`).

---

## Conventions

| Thing | Convention | Example |
|---|---|---|
| Datasets | Medallion layer | `bronze`, `silver`, `gold` |
| Bronze tables | `<source>_<entity>`; `_legacy` marks a frozen table kept as history | `mbta_alerts`, `mbta_alerts_legacy` |
| Silver models | `<bronze table>__<step>`; `__base` is the cleaned copy | `mbta_alerts__base`, `mbta_alerts__by_route` |
| Gold tables | `<domain>_<entity>` | `rail_ridership` |
| Ingest jobs | `ingest/<source>-<entity>/main.py` → `bronze.<source>_<entity>` | `ingest/noaa-weather` → `bronze.noaa_weather` |
| Bronze columns | Source system's names, plus audit columns | `route_or_line`, `tmax` |
| Silver / gold columns | `snake_case`; keys `<entity>_id`; `_at` = TIMESTAMP (UTC); `_date` = DATE (Eastern); measures carry their unit; booleans `is_` | `alert_start_at`, `precipitation_in`, `is_in_feed` |
| Audit columns | On every bronze table, carried into silver and gold where a row has one source version (alert models track `first_seen_at` / `last_seen_at` instead) | `ingested_at`, `ingested_by` |
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
| `job-scheduler` | Cloud Scheduler | Start the six Cloud Run jobs: five ingest plus the transform (`run.invoker` on each job) |
| `github-deployer` | CI/CD (GitHub Actions) | Build, push, and `terraform apply` — broad by necessity, usable only from this repo's `main` branch |

The three data workloads also hold `bigquery.jobUser` (permission to run queries), which grants no data access on its own. The MBTA API key lives in Secret Manager (`infra/secrets.tf`; Terraform owns the secret, the value is added by hand). Only the APIs the pipeline uses are enabled (`infra/apis.tf`), and Artifact Registry keeps the 5 newest versions of each image.

---

## Cost

The pipeline runs within GCP's free tiers. Query volume is dominated by BigQuery's 10 MB-per-query billing minimum (about 13 GiB/day, or 0.4 TiB/month of the free 1 TiB, measured 2026-10), not by data size, so it stays flat as history grows. A **$5/month budget** on the billing account emails at 50%, 90%, and 100% of actual spend and when spend is forecast to pass $5 (created with `gcloud billing budgets`, outside Terraform, since the CI deployer has no billing access). The budget only alerts; it never stops anything.

Hard caps bound what a runaway can cost without a billing kill switch, which would stop ingest and permanently lose live alerts:

- **BigQuery: a per-query byte limit** (`maximum_bytes_billed`): 50 GiB (~$0.30) per dbt query (`transform/profiles.yml`, local builds included) and 1 GiB per dashboard query (`serve/app.py`). A query that would bill more fails before it runs; the transform's failure sends the usual email. The dbt limit is sized for the biggest query the transform can run, a full rebuild of the alerts tables from every alert snapshot (~15 GB/year), so it holds until about mid-2030 ([roadmap](docs/roadmap.md)); hourly runs read only new snapshots.
- **Dashboard: at most 2 instances** (`infra/cloud-run-services.tf`), so a traffic flood slows the site rather than multiplying the bill. Each instance takes up to 80 concurrent connections (Cloud Run's default; one per open tab).

There is deliberately no project-wide daily query cap. One was tried on 2026-10-23 and refused queries at ~12 GiB of usage with the limit set at 50 GiB, and again at 200 GiB, so `infra/quotas.tf` pins the quota at Google's default.

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

**Stations affected** — a map of the whole network showing the stations hit right now or by planned work in the next 30 days (ringed and labeled, with each incident on hover; + / − / reset buttons to zoom, drag to pan, while the scroll wheel still scrolls the page; the OpenStreetMap/CARTO credit sits under the map), and the most-affected stations since station tracking began

**Incident patterns** — incidents per week, by line, by cause and effect, median duration by cause, cause mix by line (heatmap)

**Ridership** — per-line tiles: the latest published month's average entries per day vs the same month a year earlier (each tile names its month); 24-month trend; ridership by alert effect (delay, suspension, shuttle) vs each line's calm days; day of week

**Weather** — ridership on rainy, snowy, and unusually cold/warm days vs normal-weather days

Ridership figures are **average entries per day**, weekends included. Time windows: every section covers the trailing 12 months, except the ridership tiles (the latest published month), the ridership trend (24 months, for year-over-year), and weather (all history — storms are rare).

Incident history counts from when alert coverage became continuous (detected as the first incident after the last 14-day gap — the pre-October pipeline missed June 8 – July 1, 2026), so missing data never reads as a quiet day.

The weather charts use **% vs typical**: a day's entries vs the median for the same line, day of week, and month (federal holidays excluded), so line size, weekends, and seasons don't skew them.

The alert-effect chart uses **% vs calm days** instead: a day's entries vs the median of that line's calm days (no incident other than a station closure, which closes one stop rather than disrupting the line) on the same day of week, over the trailing 12 months of alert tracking. A monthly median would absorb a month-long shutdown into its own baseline. Bars appear only once a line has enough calm days to compare with (10 days per bar, 4 calm days per weekday), so the chart fills in by itself as alert history grows.

---

## Project Structure

```
infra/                  Terraform — all GCP infrastructure
  main.tf               Providers + GCS state backend
  variables.tf          Project, schedules, alert email, service agents
  bigquery.tf           Datasets (incl. dev sandboxes) + bronze table schemas (single source of truth)
  cloud-run-jobs.tf     Ingest jobs (one per source) + transform job
  cloud-run-services.tf Dashboard service + tylerclifton.com domain mapping
  cloud-scheduler.tf    Cron triggers
  service-accounts.tf   One service account per workload
  iam.tf                Per-workload access
  deploy.tf             GitHub Actions deploy identity (Workload Identity Federation)
  monitoring.tf         Failure alert emails
  secrets.tf            MBTA API key secret
  quotas.tf             BigQuery daily query quota, pinned at the default
  apis.tf               Enabled Google APIs
  artifact-registry.tf  Image repositories + cleanup policy
  cloud-storage.tf      Terraform state bucket
ingest/                 One shared image for every ingest job
  common/bronze.py      Shared fetch + append-to-bronze helpers
  tests/                Job tests against canned API responses
  mbta-alerts/          MBTA service alert snapshots (every 15 minutes)
  mbta-routes/          MBTA route metadata snapshots (yearly)
  mbta-stops/           MBTA station and platform snapshots (weekly)
  mbta-ridership/       ArcGIS gated entries, full history (weekly)
  noaa-weather/         NOAA GHCN-Daily for Boston Logan (daily)
transform/              dbt Core project
  run.py                Job entrypoint: dbt build + freshness, failure reports
  models/bronze/        Source declarations + freshness thresholds
  models/silver/        __base cleaned copies + steps + tests
  models/gold/          Dashboard tables (rail_incidents, rail_incident_stations, rail_stations, rail_ridership) + tests
  macros/               keep_latest_version, null_if_failed_ghcn_qc
  tests/generic/        unique_combination, accepted_range
serve/                  Streamlit dashboard (app.py; pure helpers in helpers.py, tested in tests/)
scripts/build-image.sh  Build + push a component's image (used by CI/CD)
.github/workflows/      CI/CD: lint, tests, dbt parse, terraform validate; deploy on main
requirements.txt        Local environment: every component + dev tools
pyproject.toml          pytest + ruff config
CLAUDE.md               Rules and pointers for AI coding sessions
docs/                   Setup, runbook, decision records, roadmap
```

---

## Development & Deployment

CI (`.github/workflows/ci.yml`) runs on every push and pull request without cloud credentials: ruff + pytest for the Python, `dbt parse` + sqlfluff for the SQL, and `terraform fmt` + `validate` for the infrastructure.

```bash
# Local environment (Python 3.13, as in the images; all components + dev tools)
pip install -r requirements.txt

# The same checks CI runs
ruff check ingest serve transform && pytest                            # Python
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
# plan against the deployed tag (the variables give local credentials a quota
# project; see docs/setup.md):
cd infra && USER_PROJECT_OVERRIDE=true GOOGLE_BILLING_PROJECT=mbta-reliability-analytics \
  terraform plan -var image_tag=$(git rev-parse --short=12 origin/main)

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
