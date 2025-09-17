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

# Attempt to request response from MBTA shapes API endpoint
try:
    # Make a GET request to the MBTA shapes API
    # Get all shapes data (no route_type filter available for shapes endpoint)
    # Set request to timeout after 30 seconds
    response = requests.get('https://api-v3.mbta.com/shapes?filter[route]=Red,Blue,Orange,Green-B,Green-C,Green-D,Green-E', timeout=30)
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

    # Extract shapes from the data list in the response
    shapes = data['data']

    # Create a list to store standardized shapes in
    standardized_shapes = []

    # Proceed only if any shapes exist
    if shapes:

        # Loop through each shape in the list
        for shape in shapes:

            # Extract the shape ID and attributes dictionary
            shape_id = shape.get('id', None)
            attributes = shape.get('attributes', {})

            # Extract specific shape details from the attributes dictionary
            polyline = attributes.get('polyline', None)
            
            # Record ingestion metadata
            current_datetime = datetime.datetime.now(datetime.timezone.utc)
            ingestion_timestamp = current_datetime
            ingestion_source = os.path.basename(__file__) if '__file__' in globals() else 'Unknown file name'
            
            standardized_shapes.append({
                'shape_id': shape_id,
                'polyline': polyline,
                'ingestion_timestamp': ingestion_timestamp,
                'ingestion_source': ingestion_source
            })

    else:
        # Log that no shapes exist in current response
        logging.info("No current shapes")
else:
    # The API request failed; log the HTTP status code
    logging.error(f"API request failed with status code: {response.status_code}")
    exit(1)

# Convert the list of shape dictionaries into a pandas DataFrame
output = pandas.DataFrame(standardized_shapes)

# Define BigQuery project, dataset, and table using environment variables
project_id = os.getenv('BQ_PROJECT_ID', 'mbta-reliability-analytics')
dataset_id = os.getenv('BQ_DATASET_ID', 'staging')
table_id = os.getenv('BQ_TABLE_ID', 'shapes_raw')

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