# Import standard libraries
import datetime
import logging
import os

# Import third party libraries
import pandas
from pandas_gbq import to_gbq
import requests
from google.cloud import bigquery

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize BigQuery client
client = bigquery.Client()

# Attempt to request response from MBTA routes API endpoint
try:
    # Make a GET request to the MBTA routes API
    # Filter to Red, Blue, Orange, and Green routes
    # Set request to timeout after 30 seconds
    response = requests.get('https://api-v3.mbta.com/routes?filter[id]=Red,Blue,Orange,Green-B,Green-C,Green-D,Green-E', timeout=30)

# If request times out
except requests.exceptions.Timeout:
    # Log that the request timed out
    logging.error("Request timed out")
    # Terminate Python script
    exit(1)

# Check if the request was successful (HTTP status 200)
if response.status_code == 200:

    # Convert the response JSON into a Python dictionary
    data = response.json()

    # Extract routes from the data list in the response
    routes = data['data']

    # Create a list to store standardized routes in
    standardized_routes = []

    # Proceed only if any routes exist
    if routes:

        # Loop through each route in the list
        for route in routes:

            # Extract the route ID and attributes dictionary
            route_id = route.get('id', None)
            attributes = route.get('attributes', {})

            # Extract specific route details from the attributes dictionary
            long_name = attributes.get('long_name', None)
            route_type = attributes.get('type', None)
            color = attributes.get('color', None)
            description = attributes.get('description', None)
            direction_destinations = attributes.get('direction_destinations', [])
            
            # Record ingestion metadata
            current_datetime = datetime.datetime.now(datetime.timezone.utc)
            ingestion_timestamp = current_datetime
            ingestion_source = 'mbta-ingestion-routes'
            
            # Append updated routes to list
            standardized_routes.append({
                'route_id': route_id,
                'long_name': long_name,
                'route_type': route_type,
                'color': color,
                'description': description,
                'direction_destinations': str(direction_destinations) if direction_destinations else None,
                'ingestion_source': ingestion_source,
                'ingestion_timestamp': ingestion_timestamp
            })

    else:
        # Log that no routes exist in current response
        logging.info("No current routes")
else:
    # The API request failed; log the HTTP status code
    logging.error(f"API request failed with status code: {response.status_code}")
    exit(1)

# Convert the list of route dictionaries into a pandas DataFrame
output = pandas.DataFrame(standardized_routes)

# Define BigQuery project, dataset, and table using environment variables
project_id = os.getenv('BQ_PROJECT_ID', 'mbta-reliability-analytics')
dataset_id = os.getenv('BQ_DATASET_ID', 'staging')
table_id = os.getenv('BQ_TABLE_ID', 'mbta_routes')

# Define the schema for the table
schema = [
    bigquery.SchemaField("route_id", "STRING"),
    bigquery.SchemaField("long_name", "STRING"),
    bigquery.SchemaField("route_type", "STRING"),
    bigquery.SchemaField("color", "STRING"),
    bigquery.SchemaField("description", "STRING"),
    bigquery.SchemaField("direction_destinations", "STRING"),
    bigquery.SchemaField("ingestion_source", "STRING"),
    bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP"),
]

# Ensure the table schema is consistent
client.create_table(bigquery.Table(f"{project_id}.{dataset_id}.{table_id}", schema=schema), exists_ok=True)

# Delete all rows from the staging table
query = f"DELETE FROM `{project_id}.{dataset_id}.{table_id}` WHERE TRUE"
client.query(query).result()

# Deduplicate based on unique combination of route_id
output_deduped = output.drop_duplicates(subset=['route_id'], keep='first')

# Write deduplicated data to BigQuery
try:
    # Upload the DataFrame to BigQuery (replace table if it already exists)
    to_gbq(output_deduped, f'{dataset_id}.{table_id}', project_id=project_id, if_exists='replace')
    # Log number of uploaded rows
    logging.info(f"{len(output_deduped)} rows uploaded to BigQuery")
except Exception as e:
    # Log that the BigQuery upload failed
    logging.error(f"BigQuery upload failed: {e}")
    # Terminate Python script
    exit(1)