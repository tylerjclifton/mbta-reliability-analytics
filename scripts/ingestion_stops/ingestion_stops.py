# Import standard libraries
import datetime
import logging
import os

# Import third party libraries
import pandas
import requests
from pandas_gbq import to_gbq

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    # Make a GET request to the MBTA stops API
    # Filter to light (0) and heavy (1) rail route types
    # Set request to timeout after 30 seconds
    response = requests.get('https://api-v3.mbta.com/stops?filter[route_type]=0,1', timeout=30)

except requests.exceptions.Timeout:
    # Log that the request timed out
    logging.error("Request timed out")
    # Terminate Python script
    exit(1)

# Check if the request was successful (HTTP status 200)
if response.status_code == 200:

    # Convert the response JSON into a Python dictionary
    data = response.json()

    # Extract stops from the data list in response
    stops = data['data']

    # Create a list to store standardized stops in
    standardized_stops = []

    # Proceed only if any stops exist
    if stops:

        # Loop through each stop in the list
        for stop in stops:

            # Extract the stop ID and attributes dictionary
            stop_id = stop.get('id', None)
            attributes = stop.get('attributes', {})

            # Extract specific stop details from the attributes dictionary
            address = attributes.get('address', None)
            at_street = attributes.get('at_street', None)
            description = attributes.get('description', None)
            latitude = attributes.get('latitude', None)
            location_type = attributes.get('location_type', None)
            longitude = attributes.get('longitude', None)
            municipality = attributes.get('municipality', None)
            name = attributes.get('name', None)
            on_street = attributes.get('on_street', None)
            platform_code = attributes.get('platform_code', None)
            platform_name = attributes.get('platform_name', None)
            vehicle_type = attributes.get('vehicle_type', None)
            wheelchair_boarding = attributes.get('wheelchair_boarding', None)
            
            # Record ingestion metadata
            current_datetime = datetime.datetime.now(datetime.timezone.utc)
            ingestion_timestamp = current_datetime
            ingestion_source = os.path.basename(__file__) if '__file__' in globals() else 'Unknown file name'
            
            # Create standardized stop record
            standardized_stops.append({
                'stop_id': stop_id,
                'address': address,
                'at_street': at_street,
                'description': description,
                'latitude': latitude,
                'location_type': location_type,
                'longitude': longitude,
                'municipality': municipality,
                'name': name,
                'on_street': on_street,
                'platform_code': platform_code,
                'platform_name': platform_name,
                'vehicle_type': vehicle_type,
                'wheelchair_boarding': wheelchair_boarding,
                'ingestion_timestamp': ingestion_timestamp,
                'ingestion_source': ingestion_source
            })

    else:
        # Log that no stops exist in current response
        logging.info("No current stops")
else:
    # The API request failed; log the HTTP status code
    logging.error(f"API request failed with status code: {response.status_code}")
    exit(1)

# Convert the list of stop dictionaries into a pandas DataFrame
output = pandas.DataFrame(standardized_stops)

# Define BigQuery project, dataset, and table using environment variables
project_id = os.getenv('BQ_PROJECT_ID', 'mbta-reliability-analytics')
dataset_id = os.getenv('BQ_DATASET_ID', 'staging')
table_id = os.getenv('BQ_TABLE_ID', 'stops_raw')

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