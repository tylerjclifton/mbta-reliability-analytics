# MBTA Reliability Analytics

[![CI](https://github.com/tylerjclifton/mbta-reliability-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/tylerjclifton/mbta-reliability-analytics/actions/workflows/ci.yml)

A full-stack data engineering project tracking MBTA rail reliability, ridership, and weather across the Red, Orange, Blue, and Green Lines.

**Live dashboard:** [tylerclifton.com](https://tylerclifton.com)

**Docs:** [setup on a new machine](docs/setup.md) · [runbook](docs/runbook.md) · [decision records](docs/decisions/README.md) · [roadmap](docs/roadmap.md)

---

## What it does

Ingests data from seven sources, six on an automated schedule, transforms it through a medallion architecture, and serves a live analytics dashboard.

| Source | Data | Schedule | Each run pulls |
|---|---|---|---|
| MBTA Alerts API | Service alerts (delays, suspensions, closures) | Every 15 minutes | Whole live feed, every mode (snapshot); the dashboard uses rail |
| MBTA Routes API | Route metadata (names, types, colors) | Yearly — Jan 1 | Full route list (snapshot) |
| MBTA Stops API | Stations and their platforms, with coordinates | Weekly — Mondays 6:30AM ET | Every rail station and the stops inside it (snapshot) |
| MBTA Shapes API | The path each rail line follows, for the map | Weekly — Mondays 6:45AM ET | Every shape of each rail route (snapshot) |
| NOAA GHCN-Daily | Daily temperature, precipitation, snowfall at Boston Logan | Daily — 6AM ET | Last 10 days (NOAA revises recent days) |
| MBTA LAMP archive | Every alert since 2018 (the MBTA's own archive of the alerts feed) | On demand | The whole archive; supplies alerts from before full-JSON capture ([0016](docs/decisions/0016-alerts-before-capture-from-lamp.md)) |
| MBTA ArcGIS Open Data | Gated station entries by line | Weekly — Mondays 6AM ET | Everything the layer holds, its last two years (catches revisions); 2014 – 2024-09 loaded once from the MBTA's yearly archive ([0015](docs/decisions/0015-ridership-history-from-archive.md)) |

### Data sources at a glance

Each kind of data has one live source, and history from an archive where the live source doesn't reach back. Every period comes from exactly one of them, so nothing downstream counts a record twice.

| Data | Live source | History | Seam | History starts |
|---|---|---|---|---|
| Alerts | MBTA API, every 15 minutes | MBTA LAMP archive, loaded once | Alerts seen from 2026-10-24 on (full-JSON capture) come from the API; earlier ones from LAMP | 2019-09-05 |
| Ridership | ArcGIS layer (its last two years), weekly | MBTA yearly archive, loaded once into the same table | 2024-10-01 | 2014-01-01 |
| Weather | NOAA GHCN-Daily, daily | Same source, re-pulled further back once | None | 2014-01-01 |
| Routes, stops, line shapes | MBTA API | Not kept: the MBTA archives every past schedule ([0011](docs/decisions/0011-capture-every-mode.md)) | — | Current only |

Bronze overlaps a little on purpose, since it's append-only and never trimmed ([0001](docs/decisions/0001-append-only-bronze.md)): LAMP's load and the API both hold late October 2026, and the frozen `mbta_alerts_legacy` table repeats June–October 2026. Silver takes each alert from one source only. Repeated snapshots (every alert each 15 minutes, two years of ridership each week) are how revisions and end times are captured; bronze bills compressed bytes, so they cost next to nothing ([0014](docs/decisions/0014-bronze-physical-storage-billing.md)).

The dbt transform runs hourly at :35.

---

## Dashboard

Dark theme; official MBTA line colors for every line-level visual, a neutral violet for everything else. Every line-colored mark also carries a text label. The header and footer credit the author and link to this repo.

**Service status** — KPIs (active now, planned in 30 days, last 30 days vs prior, median duration); incidents happening now and planned work coming up, one card per incident

**Stations affected** — a transit map of the whole network: every station a dot in its line's color with the line a faint path behind them, on a dimmed base map without place names, with line ends and main hubs named, showing the stations hit right now or by planned work in the next 30 days (outlined in white and labeled where the names fit, with each incident on hover; + / − / reset buttons to zoom, drag to pan, while the scroll wheel still scrolls the page; the OpenStreetMap/CARTO credit sits under the map), and the most-affected stations over the trailing 12 months

**Incident patterns** — incidents per week, by line, by cause and effect, median duration by cause, cause mix by line (heatmap)

**Disruption by year** — delays per year by how long they lasted, and hours of shuttle-bus service per year by line (overlapping diversions count once), for every full year of alert history plus the year in progress, dimmed

**Ridership** — per-line tiles: the latest published month's average entries per day vs the same month a year earlier and in 2019, the last full year before the pandemic (each tile names its month); monthly ridership, switchable between the last 2 years and all history since 2014 (each month plus a trailing 12-month average that evens out the seasons, with a few events marked); ridership by alert effect (delay, suspension, shuttle) vs each line's calm days; day of week

**Weather** — ridership on rainy, snowy, and unusually cold/warm days vs normal-weather days, all on one scale

Time windows: every section covers the trailing 12 months, except the ridership tiles (the latest published month), monthly ridership (2 years, for year-over-year, or all history), disruption by year (every full year of alert history), and weather (all history — storms are rare).

Statistics follow one rule everywhere. Volumes are averages: ridership is **average entries per day**, weekends and holidays included, because volumes add up. "Typical" values are medians: incident durations, and every baseline a comparison is made against, so a shutdown or a months-long incident can't skew them. Comparisons are like-for-like: same line, same month (so seasons and the long trend cancel), weekday-adjusted, with federal holidays left out.

Incident history counts from when alert coverage became continuous (detected as the first incident after the last 14-day gap; with the LAMP archive that's September 2019), so missing data never reads as a quiet day.

The weather charts use **% vs typical**: a day's entries vs the median for the same line, day of week, and month (federal holidays excluded), so line size, weekends, and seasons don't skew them. Each bar is the median day in its band: a line shut for most of a month has a near-zero typical that month, and its open days would swamp an average.

The alert-effect chart uses **% vs calm days** instead: a day's entries vs that line's calm days (no incident other than a station closure, which closes one stop rather than disrupting the line) in the same month, adjusted for the day of the week, over the trailing 12 months. Comparing within the month cancels seasons and the long trend; using calm days only means a shutdown never lowers its own baseline, as a plain monthly median would. Each bar is the median day, and appears once a line has 10 days of the effect and 10 calm days, in months with at least 4 calm days.

---

## Architecture

```text
MBTA Alerts API  ──┐
MBTA Routes API  ──┤
MBTA Shapes API  ──┤
MBTA Stops API   ──┤                        ┌─────────────────────────────────────────┐
NOAA GHCN-Daily  ──┼──► Cloud Run Jobs ──►  │  BigQuery                               │──► Streamlit
MBTA ArcGIS      ──┤         ↑              │  bronze → silver → gold                 │
MBTA LAMP        ──┘  Cloud Scheduler       │            └─ dbt Core ─┘               │
                                            └─────────────────────────────────────────┘
```

Everything is defined in Terraform, apart from a few documented exceptions ([0005](docs/decisions/0005-terraform-only-changes.md)), and deployed by GitHub Actions on every push to `main`.

### Medallion layers

Each layer is its own BigQuery dataset, with a dev sandbox beside it for local work (`dev_bronze`, `dev_silver`, `dev_gold`; see [Development & deployment](#development--deployment)).

| Layer | Stored as | Written by | Role |
|---|---|---|---|
| `bronze` | Append-only tables (Terraform-managed, deletion-protected; [0013](docs/decisions/0013-bronze-tables-in-terraform.md)) | Ingest jobs | Raw history. Each run appends a new version of every record it saw; rows are never updated or deleted, so nothing depends on a source keeping its own history ([0001](docs/decisions/0001-append-only-bronze.md)) |
| `silver` | Views (three incremental tables, below) | dbt | Each source's **cleaned copy** (latest version, renamed and typed, unit conversion, QC filtering), plus steps that each do **one job** (split alerts by route or station, resolve start/end, group into incidents) |
| `gold` | Tables, rebuilt hourly | dbt | Cross-source joins served to the dashboard |

| Bronze table | Grain | How it grows |
|---|---|---|
| `mbta_alerts` | alert × ingest run | The live alerts table: a 15-minute snapshot of the whole feed (every mode since 2026-10-28), each alert's full JSON — the project's own record of alerts once they end (the MBTA's LAMP archive also keeps them, less often; [roadmap](docs/roadmap.md#the-mbtas-lamp-archive)) |
| `mbta_alerts_legacy` | alert × route × ingest run | Frozen: the same snapshots as the old ingest shaped them, 2026-06-07 to 2026-10-24 (below). Never written, never deleted |
| `mbta_stops` | stop × route × ingest run | Weekly snapshot of every rail station and its platforms, entrances, and nodes |
| `mbta_shapes` | shape × route × ingest run | Weekly snapshot of the path of each rail route's patterns |
| `mbta_routes` | route × ingest run | Yearly snapshot |
| `mbta_ridership` | service date × line × ingest run | The layer's two years re-pulled weekly; days before 2024-10-01 from the yearly archive, loaded once |
| `noaa_weather` | observation date × ingest run | Last 10 days re-pulled daily (NOAA revises recent days) |
| `lamp_alerts` | alert × version × informed entity × active period × ingest run | The whole LAMP archive per load, on demand ([0016](docs/decisions/0016-alerts-before-capture-from-lamp.md)) |

Silver models are named `<bronze table>__<step>`. `__base` is each source's cleaned copy, with no business rules; every other step does one job.

| Silver model | Grain | What it is |
|---|---|---|
| `mbta_alerts__base` | alert | Each alert's latest full JSON (incremental table) |
| `mbta_alerts__by_route` | alert × route | Each alert seen since full-JSON capture began, split into one row per rail route (incremental table) |
| `lamp_alerts__base` | alert | Each rail alert's latest version in the LAMP archive, renamed toward the API's names (incremental table) |
| `lamp_alerts__by_route` | alert × route | Those LAMP alerts split into one row per rail route |
| `mbta_alerts__resolved` | alert × route | Service-affecting alerts with their real start and end, and whether they're still in the feed: from the snapshots, or from LAMP for alerts that ended before full-JSON capture |
| `mbta_alerts__grouped` | alert × route | Each alert tagged with its incident, with readable labels and durations (gold reads this; `gold.rail_incidents` has one row per incident) |
| `mbta_alerts__by_station` | alert × route × station | Which stations each alert affects, and in which direction |
| `mbta_routes__base` | route | Each rail route and the line it belongs to |
| `mbta_stops__base` | stop × route | Every station and platform, mapped to its station, with coordinates |
| `mbta_shapes__base` | shape × route | The path of each rail route's patterns, from the latest snapshot only |
| `mbta_ridership__base` | service date × line | The latest published entries, so MBTA revisions win |
| `noaa_weather__base` | observation date | Weather in °F and inches, failed quality checks removed, latest value |

| Gold table | Grain | Contents |
|---|---|---|
| `rail_incidents` | incident × route | One row per real-world event — the MBTA's re-posted/follow-up alerts collapsed (dashboard reads this), with how many stations it names |
| `rail_incident_stations` | incident × route × station | The stations each incident names, with coordinates and direction, for the map |
| `rail_stations` | station × line | Every rail station's coordinates, the map's backdrop |
| `rail_shapes` | shape × route | Each rail route's official path, for drawing the lines on the map |
| `rail_ridership` | service date × line | Gated entries, active incident count, the day's most severe alert effect, whether it was a calm day, and weather |

**`silver.mbta_alerts__by_route`, `silver.mbta_alerts__base`, and `silver.lamp_alerts__base` are tables, not views.** Everything else in silver is a view, recomputed every run ([0010](docs/decisions/0010-silver-naming-and-materialization.md)). Alert snapshots add ~15 GB/year to bronze (the whole feed, every mode; [0011](docs/decisions/0011-capture-every-mode.md)), and a view would re-read all of it for every model and test that uses alerts (~9× per transform), outgrowing the free query tier within a year. The two snapshot tables read only snapshots added since the last run, and the LAMP table reads bronze only after a new load, so cost stays flat; `dbt build --full-refresh` rebuilds them from bronze.

**Alert history: two sources.** Alerts seen since full-JSON capture began (2026-10-24, `alerts_raw_capture_start` in `dbt_project.yml`) come from the project's own snapshots: `bronze.mbta_alerts` holds each alert's full JSON as returned, for the whole feed (every mode since 2026-10-28), and silver keeps only rail ([0011](docs/decisions/0011-capture-every-mode.md)). Alerts that ended before then come from the MBTA's LAMP archive (`bronze.lamp_alerts`), from 2019-09-05 on ([0016](docs/decisions/0016-alerts-before-capture-from-lamp.md)). LAMP holds the same alerts with their stops and the MBTA's own close times, and it's more complete than the project's earlier pipeline, which missed many short alerts. That pipeline's shaped snapshots stay frozen in `bronze.mbta_alerts_legacy`; no model reads them.

**Alerts → stations.** Alerts name the stops they affect, mostly by platform and direction. `silver.mbta_alerts__by_station` unpacks that list from each alert's latest version (its full JSON, or LAMP's entities) and rolls platforms up to their station using `silver.mbta_stops__base`, one row per alert × route × station. It sits beside the alert × route models instead of changing their grain. Shuttles, suspensions, and station closures name their stations; most delays are line-wide and name none, so `gold.rail_incidents.stations_affected` is 0 for them. A few retired platforms LAMP names have no station today and are left out (model header).

**Alert end times.** An alert ends at whichever comes first: the end time the MBTA posted (an estimate, usually rounded to the hour), or when the MBTA closed it. LAMP always has the close; a snapshot has it when a run catches the alert in the few minutes it stays in the feed after closing. Otherwise a snapshot alert ends when it left the feed (midway between the last 15-minute run that saw it and the next, capped at 30 minutes after it was last seen), a few minutes after the true close ([0016](docs/decisions/0016-alerts-before-capture-from-lamp.md)). Since July 2026, 82% of alerts left the feed before their posted end.

**Alerts → incidents.** The MBTA often posts several alerts for one event (an update, or "delays due to an earlier disabled train at JFK/UMass"). `silver.mbta_alerts__grouped` groups them: same route, cause, effect, and station named in the header, starting within 2 hours of the incident's latest end (6 hours for "earlier"/"residual" follow-ups). Alerts that don't affect train service (notices, elevator/parking issues — `non_service_alert_effects` in `dbt_project.yml`) are excluded in `silver.mbta_alerts__resolved`; bronze keeps them.

---

## Data quality

The transform job (`transform/run.py`) runs `dbt build` then `dbt source freshness`:

- **Grain tests** — every silver model and gold table is unique on its key
- **Join tests** — line names are one of the four rail lines; every alert's route exists in routes
- **Range tests** — temperatures, precipitation, gated entries, and severities are physically plausible
- **Coverage** — warns if any ridership day has no weather
- **Incidents** — every incident has at least one alert and a start time
- **Unit tests** — the alert rules (end times, the 30-minute cap, the 2- and 6-hour grouping windows, what keeps incidents apart) are checked on hand-written alerts with known answers (`transform/models/silver/_silver__unit_tests.yml`), so a change that breaks a rule fails the build instead of quietly shifting the dashboard's numbers. They need BigQuery, so they run in the transform, not in CI's credential-free checks; a broken rule fails the deploy's transform run
- **Freshness** — fails the run if an ingest job stops writing to bronze (thresholds per source in `transform/models/bronze/_bronze__sources.yml`)

A failing test skips everything downstream of it, so bad data never reaches gold.

---

## Alerting

Failures email `alert_email` (`infra/variables.tf`) — never successful runs (`infra/monitoring.tf`). The billing budget emails the same account ([Cost](#cost)).

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
| Ingest scripts | Docstring (source, cadence, each run, writes to); Fetch → Shape → Load sections | |
| Python style | ruff (`pyproject.toml`): single-quoted strings; import groups sorted, each under an `# Import …` label | `# Import standard libraries` |

**Comments and docs:**
- **Comments are concise and say what the code does and why**, wherever that isn't obvious at a glance. Every model, script, and config file opens with a header: its purpose, grain (for models), and steps.
- **Logic and changing facts live in one place.** Thresholds, formulas, and figures sit next to the code that sets them; elsewhere, describe them rather than copying the number. A short repeated explanation is fine where it saves opening another file, and a pointer always comes with a one-line summary.
- **Docs change with the code**, in the same commit: README, dbt model headers and yml, `docs/`. A new decision gets a record in `docs/decisions/`.

---

## Security & access

Each workload runs as its own service account with access granted per dataset (`infra/iam.tf`). No workload has a project-wide data or admin role.

| Service account | Runs | Access |
|---|---|---|
| `ingest-jobs` | Ingest jobs | Write `bronze`; read the `mbta-api-key` secret |
| `dbt-bigquery` | Transform job | Read `bronze`; write `silver` and `gold` |
| `serve-bigquery` | Dashboard | Read `gold` |
| `job-scheduler` | Cloud Scheduler | Start the seven scheduled Cloud Run jobs: six ingest plus the transform (`run.invoker` on each job; not the on-demand `ingest-lamp-alerts`) |
| `github-deployer` | CI/CD (GitHub Actions) | Build, push, and `terraform apply` — broad by necessity, usable only from this repo's `main` branch |

The three data workloads also hold `bigquery.jobUser` (permission to run queries), and dbt holds `bigquery.user` (permission to list datasets); neither grants data access on its own. The MBTA API key lives in Secret Manager (`infra/secrets.tf`; Terraform owns the secret, the value is added by hand). Only the APIs the pipeline uses are enabled (`infra/apis.tf`), and Artifact Registry keeps the 5 newest versions of each image.

---

## Cost

The pipeline runs within GCP's free tiers. Query volume is dominated by BigQuery's 10 MB-per-query billing minimum (about 13 GiB/day, or 0.4 TiB/month of the free 1 TiB, measured 2026-10), not by data size, so it stays flat as history grows. Bronze storage is billed on compressed bytes, about 100× smaller than its raw size, so years of snapshots stay cheap to keep ([0014](docs/decisions/0014-bronze-physical-storage-billing.md)). A **$5/month budget** on the billing account emails at 50%, 90%, 100%, 200%, and 400% of actual spend ($2.50 to $20) and when spend is forecast to pass $5. Each threshold emails once per month, the first time spend crosses it, and billing data lags a few hours, so a runaway is reported within the day, not instantly. The emails go to the billing account's admin, the same Google account `alert_email` sends failure alerts to, so every alert and all of Google's account email land in one inbox. It was created with `gcloud billing budgets`, outside Terraform, since the CI deployer has no billing access. The budget only alerts; it never stops anything.

Hard caps bound what a runaway can cost without a billing kill switch, which would stop ingest and permanently lose live alerts:

- **BigQuery: a per-query byte limit** (`maximum_bytes_billed`): 50 GiB (~$0.30) per dbt query (`transform/profiles.yml`, local builds included) and 1 GiB per dashboard query (`serve/app.py`). A query that would bill more fails before it runs; the transform's failure sends the usual email. The dbt limit is sized for the biggest query the transform can run, a full rebuild of the alerts tables from every alert snapshot, so it holds until about mid-2030 ([roadmap](docs/roadmap.md)); hourly runs read only new snapshots.
- **Dashboard: at most 2 instances** (`infra/cloud-run-services.tf`), so a traffic flood slows the site rather than multiplying the bill. Each instance takes up to 80 concurrent connections (Cloud Run's default; one per open tab).

There is deliberately no project-wide daily query cap: one was tried and refused queries far below its limit, so `infra/quotas.tf` pins the quota at Google's default ([0004](docs/decisions/0004-per-query-cost-limits.md)).

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

## Project structure

```text
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
  common/run.py         What every run shares: job name, run timestamp, logging, failure reports
  common/fetch.py       fetch(): HTTP GET that fails the job cleanly (step 1)
  common/load.py        append_to_bronze(): load into bronze (step 3)
  common/mbta_api.py    MBTA API settings: base URL, rail routes, API key
  tests/                Job tests against canned API responses
  mbta-alerts/          MBTA service alert snapshots (every 15 minutes)
  mbta-routes/          MBTA route metadata snapshots (yearly)
  mbta-stops/           MBTA station and platform snapshots (weekly)
  mbta-shapes/          MBTA line shape snapshots (weekly)
  mbta-ridership/       ArcGIS gated entries, the layer's two years (weekly); yearly archive on demand
  noaa-weather/         NOAA GHCN-Daily for Boston Logan (daily)
  lamp-alerts/          The MBTA's LAMP alerts archive, whole file (on demand)
transform/              dbt Core project
  run.py                Job entrypoint: dbt build + freshness, failure reports
  models/bronze/        Source declarations + freshness thresholds
  models/silver/        __base cleaned copies + steps + data tests; unit tests for the alert rules
  models/gold/          Dashboard tables (rail_incidents, rail_incident_stations, rail_stations, rail_shapes, rail_ridership) + tests
  macros/               keep_latest_version, last_processed_snapshot, null_if_epoch, null_if_failed_ghcn_qc
  tests/generic/        unique_combination, accepted_range
serve/                  Streamlit dashboard (app.py; pure helpers in helpers.py, tested in tests/)
scripts/build-image.sh  Build + push a component's image (used by CI/CD)
.github/workflows/      CI/CD: lint, tests, dbt parse, terraform validate; deploy on main
requirements.txt        Local environment: every component + dev tools
requirements-dev.txt    Dev tool pins (ruff, sqlfluff, pytest), shared with CI
pyproject.toml          pytest + ruff config
CLAUDE.md               Rules and pointers for AI coding sessions
docs/                   Setup, runbook, decision records, roadmap
```

---

## Development & deployment

CI (`.github/workflows/ci.yml`) runs on every push and pull request without cloud credentials: ruff + pytest for the Python, `dbt parse` + sqlfluff for the SQL, and `terraform fmt` + `validate` for the infrastructure.

```bash
# Local environment (Python 3.13, as in the images; all components + dev tools)
pip install -r requirements.txt

# The same checks CI runs
ruff check ingest serve transform && pytest                            # Python
(cd transform && dbt parse --profiles-dir . && sqlfluff lint models)   # SQL
(cd infra && terraform fmt -check -recursive && terraform validate)    # Terraform

# Run an ingest job locally (writes to dev_bronze; see below)
PYTHONPATH=ingest python ingest/noaa-weather/main.py

# Build/test dbt models locally (gcloud application-default credentials;
# writes to dev_silver / dev_gold; see below)
cd transform && dbt build --profiles-dir . --target local

# Preview the dashboard against dev_gold in the production image
docker build -t serve:dev serve && docker run --rm -p 8601:8080 \
  -v ~/.config/gcloud:/root/.config/gcloud:ro -e GOOGLE_CLOUD_PROJECT=mbta-reliability-analytics \
  -e GOLD_DATASET=dev_gold serve:dev          # → http://localhost:8601

# Preview an infrastructure change against the deployed tag (the variables give
# local credentials a quota project; docs/setup.md)
cd infra && USER_PROJECT_OVERRIDE=true GOOGLE_BILLING_PROJECT=mbta-reliability-analytics \
  terraform plan -var image_tag=$(git rev-parse --short=12 origin/main)
```

Local runs never touch the live datasets. A local ingest run writes to `dev_bronze` (the same tables as bronze; rows expire after 7 days), never production bronze ([0012](docs/decisions/0012-local-ingest-writes-dev-bronze.md)); to write real bronze, run the Cloud Run job ([runbook](docs/runbook.md#run-a-job-now)). A local dbt build reads the real bronze and writes to `dev_silver` / `dev_gold`.

To ship a change, push to `main` (below). Occasional tasks (backfills, rebuilds, renames, rollbacks) are in the [runbook](docs/runbook.md).

### Continuous deployment

A push to `main` that passes CI deploys automatically (`deploy` job in `.github/workflows/ci.yml`):

1. Build the `ingest`, `transform`, and `serve` images and tag each with the commit (first 12 characters of the SHA)
2. `terraform apply -var image_tag=<commit>` — every job and the dashboard move to that commit's images
3. Run the transform once, so model changes are live immediately

GitHub authenticates to Google with **Workload Identity Federation** — a short-lived OIDC token exchanged for the `github-deployer` service account, so no keys exist anywhere. Only workflow runs on this repository's `main` branch are accepted (`infra/deploy.tf`). Rolling back is re-running the deploy for an earlier commit ([runbook](docs/runbook.md#roll-back-a-deploy)).

The deploy identity can't create itself, so `infra/deploy.tf` was applied once from a workstation (`terraform apply -var image_tag=<deployed tag>`); every apply since runs in CI.

### Terraform state

State lives in the GCS bucket `mbta-reliability-analytics-tfstate` (versioned, 30-day history; `infra/cloud-storage.tf`), configured as the backend in `infra/main.tf`. The bucket is itself managed by Terraform, so it was bootstrapped once:

1. Comment out the `backend "gcs"` block in `infra/main.tf` and `terraform apply -target=google_storage_bucket.tfstate` (state is local).
2. Restore the block and run `terraform init -migrate-state` to move the local state into the bucket.

After that, `terraform init` in `infra/` is all a new machine needs (with `gcloud auth application-default login`).
