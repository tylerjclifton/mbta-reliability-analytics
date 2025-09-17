# Import standard libraries
import datetime
import logging
import os

# Import third party libraries
import pandas
from pandas_gbq import to_gbq
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Attempt to request response from MBTA routes API endpoint
try:
    # Make a GET request to the MBTA routes API
    # Filter to light (0) and heavy (1) rail route types
    # Set request to timeout after 30 seconds
    response = requests.get('https://api-v3.mbta.com/routes?filter[type]=0,1', timeout=30)
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
            color = attributes.get('color', None)
            description = attributes.get('description', None)
            direction_destinations = attributes.get('direction_destinations', [])
            direction_names = attributes.get('direction_names', [])
            fare_class = attributes.get('fare_class', None)
            listed_route = attributes.get('listed_route', None)
            long_name = attributes.get('long_name', None)
            short_name = attributes.get('short_name', None)
            sort_order = attributes.get('sort_order', None)
            text_color = attributes.get('text_color', None)
            route_type = attributes.get('type', None)
            
            # Record ingestion metadata
            current_datetime = datetime.datetime.now(datetime.timezone.utc)
            ingestion_timestamp = current_datetime
            ingestion_source = os.path.basename(__file__) if '__file__' in globals() else 'Unknown file name'
            
            standardized_routes.append({
                'route_id': route_id,
                'color': color,
                'description': description,
                'direction_destinations': str(direction_destinations) if direction_destinations else None,
                'direction_names': str(direction_names) if direction_names else None,
                'fare_class': fare_class,
                'listed_route': listed_route,
                'long_name': long_name,
                'short_name': short_name,
                'sort_order': sort_order,
                'text_color': text_color,
                'route_type': route_type,
                'ingestion_timestamp': ingestion_timestamp,
                'ingestion_source': ingestion_source
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
table_id = os.getenv('BQ_TABLE_ID', 'routes_raw')

# Write to BigQuery
try:
    # Upload the DataFrame to BigQuery (replace table if it already exists)
    to_gbq(output, f'{dataset_id}.{table_id}', project_id=project_id, if_exists='replace')
    # Log number of uploaded rows
    logging.info(f"{len(output)} rows uploaded to BigQuery")
except Exception as e:
    # Log that the BigQuery upload failed
    logging.error(f"BigQuery upload failed: {e}")
    # Terminate Python script
    exit(1)