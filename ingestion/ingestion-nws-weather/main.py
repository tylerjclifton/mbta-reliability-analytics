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

# National Weather Service API endpoint for Boston Logan Airport
STATION_ID = 'KBOS'
NWS_API_URL = f'https://api.weather.gov/stations/{STATION_ID}/observations/latest'

# Attempt to request response from NWS API endpoint
try:
    # Make a GET request to the NWS observations API
    # Set request to timeout after 30 seconds
    # NWS requires a User-Agent header
    headers = {
        'User-Agent': '(MBTA Reliability Analytics, tyler@example.com)',
        'Accept': 'application/json'
    }
    response = requests.get(NWS_API_URL, headers=headers, timeout=30)

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

    # Extract observation properties
    properties = data.get('properties', {})

    # Create a list to store standardized weather observations
    standardized_observations = []

    # Proceed only if properties exist
    if properties:

        # Extract observation timestamp
        try:
            observation_timestamp = datetime.datetime.fromisoformat(properties.get('timestamp')) if properties.get('timestamp') else None
        except (ValueError, TypeError):
            observation_timestamp = None

        # Extract temperature (convert from Celsius to Fahrenheit for easier interpretation)
        temp_data = properties.get('temperature', {})
        temp_celsius = temp_data.get('value')
        temp_fahrenheit = (temp_celsius * 9/5) + 32 if temp_celsius is not None else None

        # Extract dewpoint
        dewpoint_data = properties.get('dewpoint', {})
        dewpoint_celsius = dewpoint_data.get('value')
        dewpoint_fahrenheit = (dewpoint_celsius * 9/5) + 32 if dewpoint_celsius is not None else None

        # Extract wind speed (m/s to mph)
        wind_data = properties.get('windSpeed', {})
        wind_ms = wind_data.get('value')
        wind_mph = wind_ms * 2.237 if wind_ms is not None else None

        # Extract wind direction
        wind_direction = properties.get('windDirection', {}).get('value')

        # Extract precipitation (last hour, in mm)
        precip_data = properties.get('precipitationLastHour', {})
        precipitation_mm = precip_data.get('value')

        # Extract relative humidity
        humidity_data = properties.get('relativeHumidity', {})
        humidity = humidity_data.get('value')

        # Extract barometric pressure
        pressure_data = properties.get('barometricPressure', {})
        pressure_pa = pressure_data.get('value')

        # Extract visibility (meters to miles)
        visibility_data = properties.get('visibility', {})
        visibility_m = visibility_data.get('value')
        visibility_miles = visibility_m * 0.000621371 if visibility_m is not None else None

        # Extract text description
        text_description = properties.get('textDescription')

        # Extract cloud layers (get lowest layer for ceiling info)
        cloud_layers = properties.get('cloudLayers', [])
        lowest_cloud_base_m = None
        lowest_cloud_amount = None
        
        if cloud_layers and len(cloud_layers) > 0:
            # Find the lowest cloud layer with actual cloud coverage (not CLR)
            for layer in cloud_layers:
                base_data = layer.get('base', {})
                base_value = base_data.get('value')
                amount = layer.get('amount')
                
                # Skip clear layers
                if amount != 'CLR' and base_value is not None:
                    if lowest_cloud_base_m is None or base_value < lowest_cloud_base_m:
                        lowest_cloud_base_m = base_value
                        lowest_cloud_amount = amount
                    break  # Take first non-clear layer as it's typically the lowest
            
            # If all layers are clear, take the first one anyway
            if lowest_cloud_base_m is None and cloud_layers:
                first_layer = cloud_layers[0]
                lowest_cloud_base_m = first_layer.get('base', {}).get('value')
                lowest_cloud_amount = first_layer.get('amount')

        # Record ingestion metadata
        current_datetime = datetime.datetime.now(datetime.timezone.utc)
        ingestion_timestamp = current_datetime
        ingestion_source = 'nws-ingestion-weather'

        # Append standardized observation
        standardized_observations.append({
            'observation_timestamp': observation_timestamp,
            'station_id': STATION_ID,
            'temperature_fahrenheit': temp_fahrenheit,
            'temperature_celsius': temp_celsius,
            'dewpoint_fahrenheit': dewpoint_fahrenheit,
            'dewpoint_celsius': dewpoint_celsius,
            'wind_speed_mph': wind_mph,
            'wind_direction_degrees': wind_direction,
            'precipitation_last_hour_mm': precipitation_mm,
            'relative_humidity_percent': humidity,
            'barometric_pressure_pa': pressure_pa,
            'visibility_miles': visibility_miles,
            'cloud_base_meters': lowest_cloud_base_m,
            'cloud_coverage': lowest_cloud_amount,
            'conditions': text_description,
            'ingestion_source': ingestion_source,
            'ingestion_timestamp': ingestion_timestamp
        })

    else:
        # Log that no observation data exists in current response
        logging.info("No observation data in response")
else:
    # The API request failed; log the HTTP status code
    logging.error(f"API request failed with status code: {response.status_code}")
    exit(1)

# Convert the list of observation dictionaries into a pandas DataFrame
output = pandas.DataFrame(standardized_observations)

# Define BigQuery project, dataset, and table using environment variables
project_id = os.getenv('BQ_PROJECT_ID', 'mbta-reliability-analytics')
dataset_id = os.getenv('BQ_DATASET_ID', 'staging')
table_id = os.getenv('BQ_TABLE_ID', 'nws_weather')

# Define the schema for the table
schema = [
    bigquery.SchemaField("observation_timestamp", "TIMESTAMP"),
    bigquery.SchemaField("station_id", "STRING"),
    bigquery.SchemaField("temperature_fahrenheit", "FLOAT"),
    bigquery.SchemaField("temperature_celsius", "FLOAT"),
    bigquery.SchemaField("dewpoint_fahrenheit", "FLOAT"),
    bigquery.SchemaField("dewpoint_celsius", "FLOAT"),
    bigquery.SchemaField("wind_speed_mph", "FLOAT"),
    bigquery.SchemaField("wind_direction_degrees", "FLOAT"),
    bigquery.SchemaField("precipitation_last_hour_mm", "FLOAT"),
    bigquery.SchemaField("relative_humidity_percent", "FLOAT"),
    bigquery.SchemaField("barometric_pressure_pa", "FLOAT"),
    bigquery.SchemaField("visibility_miles", "FLOAT"),
    bigquery.SchemaField("cloud_base_meters", "FLOAT"),
    bigquery.SchemaField("cloud_coverage", "STRING"),
    bigquery.SchemaField("conditions", "STRING"),
    bigquery.SchemaField("ingestion_source", "STRING"),
    bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP"),
]

# Ensure the table schema is consistent
client.create_table(bigquery.Table(f"{project_id}.{dataset_id}.{table_id}", schema=schema), exists_ok=True)

# Delete all rows from the staging table
query = f"DELETE FROM `{project_id}.{dataset_id}.{table_id}` WHERE TRUE"
client.query(query).result()

# Deduplicate based on unique combination of observation_timestamp and station_id
output_deduped = output.drop_duplicates(subset=['observation_timestamp', 'station_id'], keep='first')

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
