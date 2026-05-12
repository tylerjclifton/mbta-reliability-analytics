# MBTA Reliability Analytics

A data engineering project analyzing patterns in MBTA (Massachusetts Bay Transportation Authority) heavy and light rail service disruptions over time. The pipeline correlates transit alerts with route metadata and weather conditions to identify relationships between environmental factors and service reliability.

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

The Terraform configuration is located in the [infrastructure](infrastructure) directory and is **fully deployed**.

```bash
cd infrastructure
terraform init
terraform plan
terraform apply
```

## Data Pipeline

### 1. Ingestion Layer

Located in the [ingestion](ingestion) folder, containerized Python scripts collect data from external APIs and load directly into BigQuery staging tables:

#### MBTA Alerts Ingestion ([ingestion/ingestion-mbta-alerts](ingestion/ingestion-mbta-alerts))
- Fetches real-time transit alerts for subway routes
- Filters relevant service disruptions (excludes elevator/parking issues)
- Breaks out alerts by individual route for granular analysis
- Loads data directly into BigQuery staging table
- **Status**: ✅ **Deployed and Running** - Cloud Run Job executing on schedule

#### MBTA Routes Ingestion ([ingestion/ingestion-mbta-routes](ingestion/ingestion-mbta-routes))
- Retrieves route metadata (line names, types, descriptions)
- Provides enrichment data for alert analysis
- Loads data directly into BigQuery staging table
- **Status**: ✅ **Deployed and Running** - Cloud Run Job executing on schedule

#### NWS Weather Ingestion ([ingestion/ingestion-nws-weather](ingestion/ingestion-nws-weather))
- Retrieves latest weather observations from Boston Logan Airport
- Captures temperature, precipitation, wind, visibility, and cloud coverage
- Loads data directly into BigQuery staging table
- **Status**: ✅ **Deployed and Running** - Cloud Run Job executing on schedule

Each ingestion job runs as a Docker container on Cloud Run, triggered automatically by Cloud Scheduler. All jobs successfully write deduplicated data to BigQuery staging tables.

### 2. Transformation Layer

Located in the [transformation](transformation) folder, dbt Core handles data modeling and transformation:

**Status**: 🚧 **Work in Progress** - Currently migrating from GCP Dataform to dbt Core for better version control, local development, and testing capabilities

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
├── infrastructure/          # Terraform IaC (✅ Complete & Deployed)
│   ├── main.tf
│   ├── bigquery.tf
│   ├── cloud-run-jobs.tf
│   ├── cloud-scheduler.tf
│   ├── artifact-registry.tf
│   ├── service-accounts.tf
│   └── iam.tf
│
├── ingestion/              # Data collection jobs (✅ Complete & Running)
│   ├── ingestion-mbta-alerts/
│   │   ├── Dockerfile
│   │   ├── main.py        # Alert collection script
│   │   └── requirements.txt
│   ├── ingestion-mbta-routes/
│   │   ├── Dockerfile
│   │   ├── main.py        # Route metadata collection
│   │   └── requirements.txt
│   └── ingestion-nws-weather/
│       ├── Dockerfile
│       ├── main.py        # Weather data collection
│       └── requirements.txt
│
└── transformation/         # dbt Core project (🚧 In Progress - Migration from Dataform)
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
cd infrastructure
terraform plan   # Review planned changes
terraform apply  # Apply changes to GCP
```

### Running Ingestion Jobs Locally

Test ingestion scripts locally before deployment:

```bash
# Set GCP credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# Run MBTA alerts ingestion
cd ingestion/ingestion-mbta-alerts
python3 main.py

# Run MBTA routes ingestion
cd ingestion/ingestion-mbta-routes
python3 main.py

# Run NWS weather ingestion
cd ingestion/ingestion-nws-weather
python3 main.py
```

### Rebuilding and Deploying Docker Images

When you update ingestion scripts, rebuild and push images to Artifact Registry with versioned tags:

```bash
# Build for Cloud Run (AMD64 architecture required)
# Tag with both version number and latest for flexibility
cd ingestion/ingestion-mbta-alerts
docker build --platform linux/amd64 \
  -t us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-mbta-alerts:v1.0.0 \
  -t us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-mbta-alerts:latest .

# Push both tags
docker push us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-mbta-alerts:v1.0.0
docker push us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-mbta-alerts:latest

# Repeat for other ingestion jobs (mbta-routes, nws-weather)
```

**Production Best Practice:** Cloud Run jobs reference specific version tags (e.g., `v1.0.0`) in Terraform for reproducibility and rollback capability. The `latest` tag is maintained for convenience but not used in production.

**After building new versions:**
1. Update the version tag in `infrastructure/cloud-run-jobs.tf`
2. Apply Terraform changes to deploy new images:
```bash
cd infrastructure
terraform apply
```

**Note:** Images in Artifact Registry persist indefinitely and won't expire. Only rebuild when you modify the code.

### Working with dbt

The dbt transformation layer is currently being developed:

```bash
cd transformation
dbt deps         # Install dbt packages
dbt debug        # Test connection
dbt run          # Run transformations (when ready)
dbt test         # Run data quality tests
```

## Current Status

### ✅ Completed
- [x] Terraform infrastructure setup (GCP)
- [x] MBTA alerts ingestion pipeline (deployed and operational)
- [x] MBTA routes ingestion pipeline (deployed and operational)
- [x] NWS weather ingestion pipeline (deployed and operational)
- [x] Cloud Run job deployment for all ingestion workflows
- [x] Cloud Scheduler automation for scheduled data collection
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

