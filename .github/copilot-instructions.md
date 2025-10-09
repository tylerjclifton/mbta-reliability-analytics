# AI Coding Assistant Instructions

## Project Overview
This project is a data pipeline and visualization system for MBTA service reliability, consisting of:

1. Data Ingestion Services (Python)
   - Located in `scripts/ingestion_*` directories
   - Each service pulls data from MBTA's V3 API
   - Data is loaded into BigQuery staging tables
   - Services run as containerized Cloud Run jobs

2. Data Transformation Layer (Dataform)
   - All backend directories must be in root due to Dataform limitations
   - Uses Bronze → Silver → Gold pattern in `definitions/` directory
   - Key output tables:
     - `shapes`: Route geometry data
     - `stops`: Station location data
     - `gold.rail_alerts`: Processed service alerts
   - Transformations defined in `.sqlx` files
   - Dependencies managed in `workflow_settings.yaml`

3. Frontend Visualization (In Development)
   - Located in `front_end/` directory
   - Will display interactive map showing:
     - MBTA route geometries
     - Station locations
     - Current service issues/alerts
   - Consumes data from shapes, stops, and rail_alerts tables
   - Deployment:
     - Hosted on Netlify with custom domain
     - Interfaces with BigQuery for data access

## Key Architecture Patterns

### Data Ingestion Pattern
- Each ingestion service follows consistent error handling and logging
- Target routes are filtered to Red, Blue, Orange, and Green lines
- Example: `scripts/ingestion_alerts/ingestion_alerts.py`
```python
target_routes = ['Red', 'Blue', 'Orange', 'Green-B', 'Green-C', 'Green-D', 'Green-E']
```

### Data Transformation Pattern
- Bronze: Raw data from ingestion
- Silver: Cleaned and standardized data
- Gold: Business-level aggregations
- Dependencies defined in each `.sqlx` file's config block
```sql
config {
    type: 'incremental',
    schema: 'alerts',
    name: 'silver',
    tags: ['alerts'],
    dependencies: [/*...*/]
}
```

## Development Workflows

### Docker Image Updates
Build and push images to Google Artifact Registry:
```bash
docker build --platform linux/amd64 -t us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-[service]:v4 .
docker push us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-[service]:v4
```
Replace [service] with: alerts, stops, routes, or shapes

### Environment Configuration
Key environment variables:
- `BQ_PROJECT_ID`: Google Cloud project (default: mbta-reliability-analytics)
- `BQ_DATASET_ID`: BigQuery dataset name
- `BQ_TABLE_ID`: BigQuery table name (usually 'staging' for ingestion)

## Integration Points
1. MBTA V3 API
   - Timeouts set to 30 seconds
   - Rate limits not currently implemented
   - Base URL: https://api-v3.mbta.com/

2. Google Cloud Services
   - Cloud Run for ingestion jobs
   - BigQuery for data storage
   - Artifact Registry for container images
   - Dataform for transformation orchestration

## Project Structure Notes
- Backend directories must remain in root directory due to Dataform requirements
- Frontend development should be contained within `front_end/` directory
- Core data tables for visualization:
  - `shapes`: Contains route geometry for map display
  - `stops`: Contains station location data
  - `gold.rail_alerts`: Contains current service issues

## Frontend Deployment
- Website hosted on Netlify with custom domain
- BigQuery serves as the backend database
- Project structure:
  ```
  front_end/
  ├── access_bigquery_tables/  # BigQuery access layer
  └── website/                 # Netlify web application
      ├── netlify.toml        # Netlify configuration
      ├── netlify/functions/  # Serverless functions
      └── src/               # Frontend application code
  ```
- Deployment workflow:
  1. Connect repository to Netlify
  2. Configure build settings:
     - Base directory: `front_end/website`
     - Build command: `npm run build`
     - Publish directory: `dist`
  3. Set environment variables:
     - `VITE_BIGQUERY_PROJECT_ID`
     - `VITE_BIGQUERY_DATASET_ID`
     - Add other secrets in Netlify dashboard
  4. Enable automatic deployments from main branch

- Key considerations:
  - Secure BigQuery access using Netlify functions
  - CORS configuration for API endpoints
  - Rate limiting for data queries
  - Environment variable management