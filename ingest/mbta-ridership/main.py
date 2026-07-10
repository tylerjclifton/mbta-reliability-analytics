# Import standard libraries
import datetime
import logging
import os

# Import third party libraries
import pandas
import requests
from google.cloud import bigquery

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize BigQuery client
client = bigquery.Client()

# ArcGIS Feature Service endpoint for MBTA Gated Station Entries
ARCGIS_URL = 'https://services1.arcgis.com/ceiitspzDAHrdGO1/arcgis/rest/services/GSE/FeatureServer/0/query'

# Target lines — Silver Line and Mattapan excluded intentionally
TARGET_ROUTES = ['Red Line', 'Orange Line', 'Blue Line', 'Green Line']

# Calculate start date: first day of the month 3 months ago
# This keeps each quarterly run small — historical data already in BQ is not re-loaded
today = datetime.date.today()
month = today.month - 3
year = today.year
if month <= 0:
    month += 12
    year -= 1
start_date = datetime.date(year, month, 1)

logging.info(f"Pulling ridership data from {start_date} onwards")

# Build WHERE clause — filter to target routes and date window
# ArcGIS date fields use timestamp string format in WHERE clauses
routes_filter = "', '".join(TARGET_ROUTES)
where_clause = (
    f"route_or_line IN ('{routes_filter}')"
    f" AND service_date >= timestamp '{start_date} 00:00:00'"
)

# Pagination settings — ArcGIS maxRecordCount for this service is 2000
PAGE_SIZE = 2000

# Fetch all pages from the ArcGIS Feature Service
all_records = []
offset = 0

while True:
    params = {
        "where": where_clause,
        "outFields": "service_date,route_or_line,gated_entries",
        "returnGeometry": "false",
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "orderByFields": "ObjectId ASC",
        "f": "json",
    }

    # Attempt to request a page of ridership records
    try:
        response = requests.get(ARCGIS_URL, params=params, timeout=60)
    except requests.exceptions.Timeout:
        logging.error("Request timed out")
        exit(1)

    # Check if the request was successful (HTTP status 200)
    if response.status_code != 200:
        logging.error(f"API request failed with status code: {response.status_code}")
        exit(1)

    data = response.json()

    # Check for ArcGIS API-level errors
    if 'error' in data:
        logging.error(f"ArcGIS API error: {data['error']}")
        exit(1)

    features = data.get('features', [])

    # Loop through each feature returned in this page
    for feature in features:
        attrs = feature.get('attributes', {})

        # service_date is returned as epoch milliseconds from the ArcGIS date field
        service_date_raw = attrs.get('service_date')
        if isinstance(service_date_raw, (int, float)):
            try:
                service_date = datetime.datetime.fromtimestamp(
                    service_date_raw / 1000, tz=datetime.timezone.utc
                ).date()
            except (OSError, ValueError, OverflowError):
                service_date = None
        elif isinstance(service_date_raw, str):
            try:
                service_date = datetime.date.fromisoformat(service_date_raw)
            except ValueError:
                service_date = None
        else:
            service_date = None

        all_records.append({
            'service_date': service_date,
            'route_or_line': attrs.get('route_or_line'),
            'gated_entries': attrs.get('gated_entries'),
        })

    logging.info(f"Fetched {offset + len(features)} records so far...")

    # Stop paginating if there are no more records
    if not data.get('exceededTransferLimit', False):
        break

    offset += PAGE_SIZE

# Exit early if no data was returned
if not all_records:
    logging.info("No ridership data returned from ArcGIS")
    exit(0)

# Build DataFrame from collected records
df = pandas.DataFrame(all_records)

# Explicitly cast metric columns to float so pandas never infers int64,
# which would cause BigQuery schema mismatches when decimal values arrive
# (ArcGIS stores gated_entries as a string; split stations can have decimal values)
df['gated_entries'] = pandas.to_numeric(df['gated_entries'], errors='coerce').astype(float)

# Aggregate by service_date and route_or_line — this collapses stop-level and
# time-period granularity into a single daily total per line
df_aggregated = (
    df
    .groupby(['service_date', 'route_or_line'], as_index=False)['gated_entries']
    .sum()
    .rename(columns={'gated_entries': 'total_gated_entries'})
)

# Record ingestion metadata
ingestion_timestamp = datetime.datetime.now(datetime.timezone.utc)
df_aggregated['ingestion_source'] = 'mbta-ingestion-ridership'
df_aggregated['ingestion_timestamp'] = ingestion_timestamp

# Define BigQuery project, dataset, and table using environment variables
project_id = os.getenv('BQ_PROJECT_ID', 'mbta-reliability-analytics')
dataset_id = os.getenv('BQ_DATASET_ID', 'staging')
table_id = os.getenv('BQ_TABLE_ID', 'mbta_ridership')

# Define the schema for the BigQuery table
schema = [
    bigquery.SchemaField("service_date", "DATE"),
    bigquery.SchemaField("route_or_line", "STRING"),
    bigquery.SchemaField("total_gated_entries", "FLOAT"),
    bigquery.SchemaField("ingestion_source", "STRING"),
    bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP"),
]

# Deduplicate on service_date + route_or_line before loading — groupby above
# should already produce unique rows, but this guards against any API quirks
output_deduped = df_aggregated.drop_duplicates(subset=['service_date', 'route_or_line'], keep='first')

# Write deduplicated data to BigQuery
# WRITE_TRUNCATE replaces the table atomically and enforces the explicit schema,
# preventing pandas type inference from creating mismatched column types
try:
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    load_job = client.load_table_from_dataframe(
        output_deduped,
        f"{project_id}.{dataset_id}.{table_id}",
        job_config=job_config
    )
    load_job.result()
    logging.info(f"{len(output_deduped)} rows uploaded to BigQuery")
except Exception as e:
    logging.error(f"BigQuery upload failed: {e}")
    exit(1)