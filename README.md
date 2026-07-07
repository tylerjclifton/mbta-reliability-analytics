# MBTA Reliability Analytics

A full-stack data engineering project that ingests MBTA transit alerts and NWS weather observations, transforms them through a medallion architecture in dbt, and serves a live analytics dashboard exploring the relationship between weather conditions and subway reliability.

**Live dashboard:** [tylerclifton.com](https://tylerclifton.com)

---

## Architecture

```
MBTA Alerts API ──┐
MBTA Routes API ──┼──► Cloud Run Jobs ──► BigQuery (staging) ──► dbt Core ──► BigQuery (gold) ──► Streamlit Dashboard
NWS Weather API ──┘         ↑
                     Cloud Scheduler
                    (twice daily, 7am/7pm ET)
```

The pipeline follows an **ELT** pattern with a **medallion architecture**:

| Layer | Description |
|---|---|
| **Bronze** | Raw API data standardized into consistent schemas |
| **Silver** | Cleaned, deduplicated, and enriched models (alerts + routes joined; weather cleaned) |
| **Gold** | Analytical model — MBTA alerts joined with daily weather observations |

---

## Stack

| Category | Technology |
|---|---|
| Cloud Platform | Google Cloud Platform (GCP) |
| Infrastructure as Code | Terraform |
| Data Warehouse | BigQuery |
| Ingestion Compute | Cloud Run Jobs |
| Scheduling | Cloud Scheduler |
| Transformation | dbt Core |
| Dashboard | Streamlit (Cloud Run Service) |
| Containerization | Docker |
| Container Registry | Artifact Registry |
| Languages | Python, SQL |

---

## Project Structure

```
.
├── infra/                        # Terraform — all GCP infrastructure
│   ├── main.tf
│   ├── variables.tf
│   ├── bigquery.tf
│   ├── artifact-registry.tf
│   ├── cloud-run-jobs.tf         # Ingestion + transform jobs
│   ├── cloud-run-services.tf     # Streamlit dashboard service
│   ├── cloud-scheduler.tf
│   ├── service-accounts.tf
│   ├── iam.tf
│   └── apis.tf
│
├── ingest/                       # Containerized ingestion jobs
│   ├── mbta-alerts/              # MBTA service alert ingestion
│   ├── mbta-routes/              # MBTA route metadata ingestion
│   └── nws-weather/              # NWS Boston Logan weather ingestion
│
├── transform/                    # dbt Core project
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── models/
│   │   ├── mbta/                 # Bronze + silver MBTA models
│   │   ├── nws/                  # Bronze + silver weather models
│   │   └── gold/                 # mbta_alerts_with_weather (final)
│   ├── macros/                   # Bronze/silver/gold builders + utils
│   └── deployment/               # Dockerfile + deploy.sh for Cloud Run
│
├── serve/                        # Streamlit analytics dashboard
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
│
└── requirements.txt              # Local dev dependencies (dbt, testing, notebooks)
```

---

## Data Sources

| Source | What it provides |
|---|---|
| [MBTA Alerts API](https://www.mbta.com/developers/v3-api) | Real-time service alerts for Red, Blue, Orange, and Green Line routes |
| [MBTA Routes API](https://www.mbta.com/developers/v3-api) | Route metadata (names, types, service characteristics) |
| [NWS KBOS Observations](https://api.weather.gov/stations/KBOS/observations) | Hourly weather at Boston Logan Airport — temperature, precipitation, wind, visibility |

---

## Dashboard

The dashboard is publicly accessible at [tylerclifton.com](https://tylerclifton.com) and served via Cloud Run (scales to zero when idle).

**Sections:**
- **KPIs** — Active alerts, routes currently affected, alerts this month, avg alert duration
- **Active Alerts** — Live table of open alerts with route, cause, effect, and description
- **Alert History** — Full searchable/filterable table of all past and present alerts
- **Alerts By Route / Alerts By Month** — Volume trends by route and over time
- **Alert Causes / Alert Cause By Route** — What triggers alerts and which lines are affected
- **Daily Alerts vs Temperature / Precipitation** — Scatter plots with OLS trendlines to test weather correlation

---

## Infrastructure

All infrastructure is managed with Terraform. Current deployed versions:

| Component | Image |
|---|---|
| `ingest-mbta-alerts` | `backend/ingest-mbta-alerts:v1.0.0` |
| `ingest-mbta-routes` | `backend/ingest-mbta-routes:v1.0.0` |
| `ingest-nws-weather` | `backend/ingest-nws-weather:v1.0.0` |
| `transform` | `backend/transform:v1.0.1` |
| `serve` (dashboard) | `frontend/serve:v1.0.3` |

```bash
cd infra
terraform init
terraform plan
terraform apply
```

---

## Local Development

### Prerequisites
- Python 3.9+
- Docker
- Terraform 1.5+
- GCP service account with appropriate roles

### Setup

```bash
git clone https://github.com/tylerjclifton/mbta-reliability-analytics.git
cd mbta-reliability-analytics
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running Ingestion Locally

```bash
export GOOGLE_APPLICATION_CREDENTIALS="keys/gcp-dbt-sa.json"

cd ingest/mbta-alerts && python main.py
cd ingest/mbta-routes && python main.py
cd ingest/nws-weather && python main.py
```

### Running dbt Locally

```bash
cd transform
dbt deps
dbt debug       # verify connection
dbt run         # run all models
dbt test        # run data quality tests
```

### Running the Dashboard Locally

```bash
cd serve
pip install -r requirements.txt
export GOOGLE_APPLICATION_CREDENTIALS="../keys/gcp-dbt-sa.json"
streamlit run app.py
```

### Deploying New Versions

**Ingestion jobs:**
```bash
cd ingest/mbta-alerts
docker build --platform linux/amd64 \
  -t us-east1-docker.pkg.dev/mbta-reliability-analytics/backend/ingest-mbta-alerts:v1.0.1 .
docker push us-east1-docker.pkg.dev/mbta-reliability-analytics/backend/ingest-mbta-alerts:v1.0.1
# Update tag in infra/cloud-run-jobs.tf, then terraform apply
```

**Transform pipeline:**
```bash
cd transform/deployment
bash deploy.sh v1.0.2
# Update tag in infra/cloud-run-jobs.tf, then terraform apply
```

**Dashboard:**
```bash
docker build --platform linux/amd64 \
  -t us-east1-docker.pkg.dev/mbta-reliability-analytics/frontend/serve:v1.0.3 ./serve
docker push us-east1-docker.pkg.dev/mbta-reliability-analytics/frontend/serve:v1.0.3
gcloud run services update serve --region us-east1 \
  --image us-east1-docker.pkg.dev/mbta-reliability-analytics/frontend/serve:v1.0.3
# Update tag in infra/cloud-run-services.tf, then terraform apply
```

---

## License

For educational and analytical purposes.


## Project Overview

This project investigates whether weather conditions correlate with increased MBTA service disruptions. By enriching transit alert data with route information and weather observations from Boston Logan Airport, the analysis explores patterns in subway/light rail reliability across different conditions. The data pipeline is built entirely on Google Cloud Platform (GCP) with automated ingestion and transformation.

### Data Sources

- **MBTA Alerts API**: Real-time service alerts for Red, Blue, Orange, and Green Line routes (filtered to exclude non-service issues like elevator closures)
- **MBTA Routes API**: Route metadata including line names, types, and service characteristics for enrichment
- **National Weather Service API**: Hourly weather observations from Boston Logan Airport (KBOS) including temperature, precipitation, wind, and visibility

### Analytical Approach

1. **Ingest MBTA alerts** by route over time to track service disruptions
2. **Enrich alerts** with route metadata (line names, service types, etc.)
3. **Join with weather data** to identify temporal overlaps between weather conditions and alert patterns
4. **Analyze correlations** between environmental factors and service disruptions

## Architecture

The project follows a modern ELT (Extract, Load, Transform) pattern:

```
MBTA API + NWS API → Cloud Run Jobs → BigQuery → dbt Core → Analytics
```

### Infrastructure (GCP)

All infrastructure is managed as code using **Terraform** and includes:

- **BigQuery**: Data warehouse for storing raw and transformed data
- **Cloud Run Jobs**: Serverless job execution for data ingestion
  - MBTA Alerts ingestion job
  - NWS Weather ingestion job
- **Cloud Scheduler**: Automated job triggering on regular intervals
- **Service Accounts**: Secure credential management with least-privilege IAM roles
- **Artifact Registry**: Container image storage for ingestion jobs

#### Infrastructure Setup

The Terraform configuration is located in the [infra](infra) directory and is **fully deployed**.

```bash
cd infra
terraform init
terraform plan
terraform apply
```

## Data Pipeline

### 1. Ingestion Layer

Located in the [ingest](ingest) folder, containerized Python scripts collect data from external APIs and load directly into BigQuery staging tables:

#### MBTA Alerts Ingestion ([ingest/mbta-alerts](ingest/mbta-alerts))
- Fetches real-time transit alerts for subway routes
- Filters relevant service disruptions (excludes elevator/parking issues)
- Breaks out alerts by individual route for granular analysis
- Loads data directly into BigQuery staging table
- **Status**: ✅ **Deployed and Running** - Cloud Run Job executing on schedule

#### MBTA Routes Ingestion ([ingest/mbta-routes](ingest/mbta-routes))
- Retrieves route metadata (line names, types, descriptions)
- Provides enrichment data for alert analysis
- Loads data directly into BigQuery staging table
- **Status**: ✅ **Deployed and Running** - Cloud Run Job executing on schedule

#### NWS Weather Ingestion ([ingest/nws-weather](ingest/nws-weather))
- Retrieves latest weather observations from Boston Logan Airport
- Captures temperature, precipitation, wind, visibility, and cloud coverage
- Loads data directly into BigQuery staging table
- **Status**: ✅ **Deployed and Running** - Cloud Run Job executing on schedule

Each ingestion job runs as a Docker container on Cloud Run, triggered automatically by Cloud Scheduler. All jobs successfully write deduplicated data to BigQuery staging tables.

### 2. Transformation Layer

Located in the [transform](transform) folder, dbt Core handles data modeling and transformation:

**Status**: 🚧 **Work in Progress** - dbt Core models built and deployed to Cloud Run, currently validating data quality and accumulating historical data

The transformation layer uses a **medallion architecture**:
- **Bronze**: Raw data from APIs with minimal transformation (standardization only)
- **Silver**: Cleaned, deduplicated, and conformed data models
  - `mbta_silver`: Alerts enriched with route metadata
  - `nws_silver`: Cleaned weather observations
- **Gold**: Business-ready analytical models
  - `mbta_alerts_with_weather`: MBTA alerts joined with weather conditions to identify temporal patterns and correlations

**Planned dbt models:**
- `mbta_bronze_alerts.sql`: Standardized raw alert data
- `mbta_bronze_routes.sql`: Standardized raw route data
- `nws_bronze_weather.sql`: Standardized raw weather data
- `mbta_silver.sql`: Alerts enriched with route information
- `nws_silver.sql`: Cleaned weather with derived metrics
- `mbta_alerts_with_weather.sql`: Final analytical model joining all data sources

## Project Structure

```
.
├── infra/                  # Terraform IaC (✅ Complete & Deployed)
│   ├── main.tf
│   ├── bigquery.tf
│   ├── cloud-run-jobs.tf
│   ├── cloud-scheduler.tf
│   ├── artifact-registry.tf
│   ├── service-accounts.tf
│   └── iam.tf
│
├── ingest/                 # Data collection jobs (✅ Complete & Running)
│   ├── mbta-alerts/
│   │   ├── Dockerfile
│   │   ├── main.py        # Alert collection script
│   │   └── requirements.txt
│   ├── mbta-routes/
│   │   ├── Dockerfile
│   │   ├── main.py        # Route metadata collection
│   │   └── requirements.txt
│   └── nws-weather/
│       ├── Dockerfile
│       ├── main.py        # Weather data collection
│       └── requirements.txt
│
└── transform/              # dbt Core project (🚧 In Progress - Migration from Dataform)
    ├── dbt_project.yml
    ├── profiles.yml
    ├── models/
    │   ├── mbta/          # MBTA data models (bronze & silver)
    │   ├── nws/           # Weather data models (bronze & silver)
    │   └── gold/          # Final analytical models
    └── macros/            # Custom dbt macros and configurations
```

## Getting Started

### Prerequisites

- Python 3.9+
- Google Cloud Platform account
- Terraform 1.5+
- Docker (for containerized ingestion jobs)
- dbt Core (for transformations)

### Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd mbta-reliability-analytics
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Deploying Infrastructure

The Terraform infrastructure is fully configured and deployed. To make changes:

```bash
cd infra
terraform plan   # Review planned changes
terraform apply  # Apply changes to GCP
```

### Running Ingestion Jobs Locally

Test ingestion scripts locally before deployment:

```bash
# Set GCP credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# Run MBTA alerts ingestion
cd ingest/mbta-alerts
python3 main.py

# Run MBTA routes ingestion
cd ingest/mbta-routes
python3 main.py

# Run NWS weather ingestion
cd ingest/nws-weather
python3 main.py
```

### Rebuilding and Deploying Docker Images

**Current Deployed Versions:**
- `ingestion-mbta-alerts`: v1.0.0
- `ingestion-mbta-routes`: v1.0.0
- `ingestion-nws-weather`: v1.0.0
- `transform-pipeline`: v1.0.1

When you update code, rebuild and push images to Artifact Registry with versioned tags:

**For ingestion jobs:**
```bash
# Build for Cloud Run (AMD64 architecture required)
cd ingest/mbta-alerts
docker build --platform linux/amd64 \
  -t us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-mbta-alerts:v1.0.1 .

# Push to Artifact Registry
docker push us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-mbta-alerts:v1.0.1

# Repeat for other ingestion jobs (mbta-routes, nws-weather)
```

**For transformation pipeline:**
```bash
# Use the deployment script (includes build, push, and instructions)
cd transform/deployment
bash deploy.sh v1.0.2  # Or specify your version
```

**Production Best Practice:** Cloud Run jobs reference specific version tags (e.g., `v1.0.0`) in Terraform for reproducibility and rollback capability.

**After building new versions:**
1. Update the version tag in `infra/cloud-run-jobs.tf`
2. Apply Terraform changes to deploy new images:
```bash
cd infra
terraform apply
```

**Note:** Images in Artifact Registry persist indefinitely and won't expire. Only rebuild when you modify the code.


### Working with dbt

For local development and deployment, see the in-repo configuration files for detailed, well-commented settings:

- [transform/profiles.yml](transform/profiles.yml): dbt connection and environment settings
- [transform/dbt_project.yml](transform/dbt_project.yml): dbt project structure and paths

**Common dbt commands:**
```bash
cd transform  # Enter dbt project directory
source ../venv/bin/activate  # Activate Python virtual environment
dbt deps           # Install dbt packages
dbt debug          # Test dbt connection
dbt run            # Run all dbt models
dbt test           # Run dbt data quality tests
```

**Deployment:**
See [transform/deployment/deploy.sh](transform/deployment/deploy.sh) and in-file comments for build and deployment steps.

## Current Status

### ✅ Completed
- [x] Terraform infrastructure setup (GCP)
- [x] MBTA alerts ingestion pipeline (deployed and operational)
- [x] MBTA routes ingestion pipeline (deployed and operational)
- [x] NWS weather ingestion pipeline (deployed and operational)
- [x] Cloud Run job deployment for all ingestion workflows
- [x] Cloud Scheduler automation for scheduled data collection
- [x] dbt Core transformation pipeline with medallion architecture (bronze/silver/gold)
- [x] Automated Cloud Run deployment for dbt transformations
- [x] Data quality and join validation (alerts+routes, alerts+weather)
- [x] BigQuery data warehouse setup with staging tables

### 🚧 In Progress
- [ ] **dbt Core transformation layer** (currently migrating from GCP Dataform to dbt Core for improved version control and local development)
- [ ] Bronze layer models (raw data standardization)
- [ ] Silver layer models (cleaned and enriched data)
- [ ] Gold layer analytical models (alerts enriched with routes + weather)

### 📋 Planned
- [ ] Data quality tests
- [ ] dbt documentation generation
- [ ] Dashboard/visualization layer
- [ ] CI/CD pipeline for automated deployments

## Technologies Used

- **Cloud Platform**: Google Cloud Platform (GCP)
- **Infrastructure as Code**: Terraform
- **Data Warehouse**: BigQuery
- **Compute**: Cloud Run Jobs
- **Orchestration**: Cloud Scheduler
- **Transformation**: dbt Core (migrating from GCP Dataform)
- **Languages**: Python, SQL
- **Containerization**: Docker
- **Container Registry**: Google Artifact Registry

## Project Goals & Expected Insights

This project aims to answer key questions about MBTA service reliability:

**Primary Research Questions:**
- Do specific weather conditions (precipitation, temperature extremes, wind) correlate with increased service disruptions?
- Which MBTA routes are most affected by weather-related service issues?
- Are there temporal patterns in service disruptions (time of day, day of week, season)?
- How do heavy vs. light rail lines differ in weather sensitivity?

**Expected Deliverables:**
- Historical dataset of MBTA alerts enriched with route and weather context
- Analytical models showing correlations between environmental factors and service disruptions
- Foundation for predictive modeling or real-time monitoring dashboards

## License

This project is for educational and analytical purposes.

## Contact

For questions or contributions, please open an issue in the repository.

