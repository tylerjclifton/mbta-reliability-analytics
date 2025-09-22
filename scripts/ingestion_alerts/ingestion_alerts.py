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

# Attempt to request response from MBTA alerts API endpoint
try:
    # Make a GET request to the MBTA alerts API
    # Commented out API call with filter since Green and Red lines don't come through when using it
    # Set request to timeout after 30 seconds
    # response = requests.get('https://api-v3.mbta.com/alerts?filter[route_type]=0,1', timeout=30)
    response = requests.get('https://api-v3.mbta.com/alerts', timeout=30)
# If request times out
except requests.exceptions.Timeout:
    # Log that the request timed out
    logging.error("Request timed out")
    # Terminate Python script
    exit(1)

# Create list of routes to get alerts for
target_routes = ['Red', 'Blue', 'Orange', 'Green-B', 'Green-C', 'Green-D', 'Green-E', 'Mattapan']

# Create list of effects to exclude from api call
exclude_effects = ['STATION_ISSUE', 'ESCALATOR_CLOSURE', 'ELEVATOR_CLOSURE', 'PARKING_CLOSURE', 'PARKING_ISSUE', 'BIKE_ISSUE', 'DOCK_CLOSURE', 'DOCK_ISSUE', 'EXTRA_SERVICE']

# Check if the request was successful (HTTP status 200)
if response.status_code == 200:

    # Convert the response JSON into a Python dictionary
    data = response.json()

    # Extract alerts from the data list in the response
    alerts = data['data']

    # Create a list to store standardized alerts in
    standardized_alerts = []

    # Proceed only if any alerts exist
    if alerts:

        # Loop through each alert in the list
        for alert in alerts:

            # Extract the alert ID and attributes dictionary
            alert_id = alert.get('id', None)
            attributes = alert.get('attributes', {})

            # Extract specific alert details from the attributes dictionary
            informed_entity = attributes.get('informed_entity', [])
            header = attributes.get('header', None)
            description = attributes.get('description', None)
            active_period = attributes.get('active_period', [])
            duration_certainty = attributes.get('duration_certainty', None)
            cause = attributes.get('cause', None)
            effect = attributes.get('effect', None)
            service_effect = attributes.get('service_effect', None)
            severity = attributes.get('severity', None)
            lifecycle = attributes.get('lifecycle', None)
            created_at = attributes.get('created_at', None)
            updated_at = attributes.get('updated_at', None)
            
            # Extract the start and end timestamps of the alert, if available
            if active_period:
                # Use first available active_period (in case multiple are provided by MBTA)
                period = active_period[0]
                # Try to get extract start value from active_period
                try:
                    # Attempt to parse the start value into a Python timestamps object
                    # If the value is missing → default to None
                    active_period_start = datetime.datetime.fromisoformat(period.get('start')) if period.get('start') else None
                # If the value exists but is malformed
                except (ValueError, TypeError):
                    # Set to None
                    active_period_start = None
                # Try to extract end value from active_period
                try:
                    # Attempt to parse the end value into a Python datetime object
                    active_period_end = datetime.datetime.fromisoformat(period.get('end')) if period.get('end') else None
                # If the value exists but is malformed
                except (ValueError, TypeError):
                    # Set to None
                    active_period_end = None
            # If no active_period is provided, default both start and end timestamps to None
            else:
                active_period_start = None
                active_period_end = None
            
            # Record ingestion metadata
            current_datetime = datetime.datetime.now(datetime.timezone.utc)
            ingestion_timestamp = current_datetime
            ingestion_source = os.path.basename(__file__) if '__file__' in globals() else 'Unknown file name'
            
            # If the alert affects any routes, create one row per route and stop
            has_entity = False
            for entity in informed_entity:
                route = entity.get('route')
                stop = entity.get('stop')
                if route and route in target_routes and effect not in exclude_effects:
                    has_entity = True
                    standardized_alerts.append({
                        'alert_id': alert_id,
                        'active_period_start': active_period_start,
                        'active_period_end': active_period_end,
                        'duration_certainty': duration_certainty,
                        'route': route,
                        'stop': stop,
                        'header': header,
                        'description': description,
                        'cause': cause,
                        'effect': effect,
                        'service_effect': service_effect,
                        'severity': severity,
                        'lifecycle': lifecycle,
                        'created_at': created_at,
                        'updated_at': updated_at,
                        'ingestion_timestamp': ingestion_timestamp,
                        'ingestion_source': ingestion_source
                    })

    else:
        # Log that no alerts exist in current response
        logging.info("No current alerts")
else:
    # The API request failed; log the HTTP status code
    logging.error(f"API request failed with status code: {response.status_code}")
    exit(1)

# Convert the list of alert dictionaries into a pandas DataFrame
output = pandas.DataFrame(standardized_alerts)

# Define BigQuery project, dataset, and table using environment variables
project_id = os.getenv('BQ_PROJECT_ID', 'mbta-reliability-analytics')
dataset_id = os.getenv('BQ_DATASET_ID', 'staging')
table_id = os.getenv('BQ_TABLE_ID', 'alerts_raw')

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