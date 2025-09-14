# Import standard libraries
import datetime
import os

# Import third party libraries
import pandas
import requests
from pandas_gbq import to_gbq

# Make a GET request to the MBTA alerts API
# Filter to light (0) and heavy (1) rail route types
response = requests.get('https://api-v3.mbta.com/alerts?filter[route_type]=0,1')

# Check if the request was successful (HTTP status 200)
if response.status_code == 200:

    # Convert the response JSON into a Python dictionary
    data = response.json()

    # Extract the list of alerts from the response
    alerts = data['data']

    # Proceed only if there are any alerts
    if alerts:
        standardized_alerts = []

        # Loop through each alert in the list
        for alert in alerts:

            # Safely extract the alert ID and attributes dictionary
            alert_id = alert.get('id', 'No alert id')
            attributes = alert.get('attributes', {})

            # Extract specific alert details from the attributes dictionary
            informed_entity = attributes.get('informed_entity', [])
            header = attributes.get('header', 'No header')
            description = attributes.get('description', 'No description')
            active_period = attributes.get('active_period', [])
            cause = attributes.get('cause', 'No cause')
            effect = attributes.get('effect', 'No effect')
            severity = attributes.get('severity', 'No severity')
            lifecycle = attributes.get('lifecycle', 'No lifecycle')
            
            # Extract the start and end times of the alert, if available
            if active_period:
                period = active_period[0] # Get first available active_period in case multiple exist
                active_period_start = datetime.datetime.fromisoformat(period.get('start')) if period.get('start') else None
                active_period_end = datetime.datetime.fromisoformat(period.get('end')) if period.get('end') else None
            else:
                active_period_start = None
                active_period_end = None
            
            # Record metadata about ingestion
            current_datetime = datetime.datetime.now()
            ingestion_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
            ingestion_source = os.path.basename(__file__) if '__file__' in globals() else 'Issue getting file name'
            
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
                        'ingestion_datetime': ingestion_datetime,
                        'ingestion_source': ingestion_source
                    })
            
            # If no routes are listed, add a single row with 'No route'
            if not has_route:
                standardized_alerts.append({
                    'alert_id': alert_id,
                    'active_period_start': active_period_start,
                    'active_period_end': active_period_end,
                    'route': 'No route',
                    'header': header,
                    'description': description,
                    'cause': cause,
                    'effect': effect,
                    'severity': severity,
                    'lifecycle': lifecycle,
                    'ingestion_datetime': ingestion_datetime,
                    'ingestion_source': ingestion_source
                })

    else:
        # No alerts found in the response
        print("No current alerts.")
else:
    # The API request failed; print the HTTP status code
    print(f"Error: {response.status_code}")

# Convert the list of alert dictionaries into a pandas DataFrame
output = pandas.DataFrame(standardized_alerts)

# Define BigQuery project, dataset, and table
project_id = 'mbta-reliability-analytics'
dataset_id = 'staging'
table_id = 'alerts_raw'

# Upload the DataFrame to BigQuery (replace table if it already exists)
to_gbq(output, f'{dataset_id}.{table_id}', project_id=project_id, if_exists='replace')

# Print number of uploaded rows
print(f"{len(output)} rows uploaded to BigQuery.")