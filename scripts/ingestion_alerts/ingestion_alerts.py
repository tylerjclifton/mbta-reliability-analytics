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
    # Make a GET request to the MBTA alerts API
    # Filter to light (0) and heavy (1) rail route types
    # Set request to timeout after 30 seconds
    response = requests.get('https://api-v3.mbta.com/alerts?filter[route_type]=0,1', timeout=30)

except requests.exceptions.Timeout:
    # Log that the request timed out
    logging.error("Request timed out")
    # Terminate Python script
    exit(1)

# Check if the request was successful (HTTP status 200)
if response.status_code == 200:

    # Convert the response JSON into a Python dictionary
    data = response.json()

    # Extract alerts from the data list in response
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
            cause = attributes.get('cause', None)
            effect = attributes.get('effect', None)
            severity = attributes.get('severity', None)
            lifecycle = attributes.get('lifecycle', None)
            
            # Extract the start and end datetimes of the alert, if available
            if active_period:
                # Use first available active_period (in case multiple are provided by MBTA)
                period = active_period[0]
                try:
                    # Attempt to parse the 'start' field into a Python datetime object
                    # If the field is missing → default to None
                    active_period_start = datetime.datetime.fromisoformat(period.get('start')) if period.get('start') else None
                except (ValueError, TypeError):
                    # If the field exists but is malformed → catch the error and set None
                    active_period_start = None
                try:
                    # Attempt to parse the 'end' field into a Python datetime object
                    active_period_end = datetime.datetime.fromisoformat(period.get('end')) if period.get('end') else None
                except (ValueError, TypeError):
                    # Same safeguards as above to ensure ingestion doesn't fail on bad data
                    active_period_end = None
            # If no active_period is provided, default both start and end datetimes to None
            else:
                active_period_start = None
                active_period_end = None
            
            # Record ingestion metadata
            current_datetime = datetime.datetime.now(datetime.timezone.utc)
            ingestion_timestamp = current_datetime.isoformat()
            ingestion_source = os.path.basename(__file__) if '__file__' in globals() else 'Unknown file name'
            
            # If the alert affects any routes, create one row per route
            has_route = False
            for entity in informed_entity:
                route = entity.get('route')
                if route:
                    has_route = True
                    standardized_alerts.append({
                        'alert_id': alert_id,
                        'active_period_start': active_period_start,
                        'active_period_end': active_period_end,
                        'route': route,
                        'header': header,
                        'description': description,
                        'cause': cause,
                        'effect': effect,
                        'severity': severity,
                        'lifecycle': lifecycle,
                        'ingestion_timestamp': ingestion_timestamp,
                        'ingestion_source': ingestion_source
                    })
            
            # If no routes are listed, set route as None
            if not has_route:
                standardized_alerts.append({
                    'alert_id': alert_id,
                    'active_period_start': active_period_start,
                    'active_period_end': active_period_end,
                    'route': None,
                    'header': header,
                    'description': description,
                    'cause': cause,
                    'effect': effect,
                    'severity': severity,
                    'lifecycle': lifecycle,
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