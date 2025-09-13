# Import standard libraries
import datetime
import os

# Import third party libraries
import pandas
import requests
from pandas_gbq import to_gbq

# Set routes to pull schedules for
routes = ['Red', 'Orange', 'Blue']

# Initialize the list at the top level
standardized_schedules = []

# Make a GET request to the MBTA schedules API
response = requests.get('https://api-v3.mbta.com/schedules',
                        params={'filter[route]': routes, 'page[limit]': '500'})

# Check if the request was successful (HTTP status 200)
if response.status_code == 200:

    # Convert the response JSON into a Python dictionary
    data = response.json()

    # Extract the list of schedules from the response
    schedules = data['data']

    # Proceed only if there are any schedules
    if schedules:

        # Loop through each prediction in the list
        for prediction in schedules:

            # Safely extract the prediction ID, attributes dictionary, and relationships object
            prediction_id = prediction.get('id', 'No prediction ID')
            attributes = prediction.get('attributes', {})
            relationships = prediction.get('relationships', {})

            # Extract specific prediction details from the attributes dictionary
            arrival_time = attributes.get('arrival_time', None)
            arrival_uncertainty = attributes.get('arrival_uncertainty', None)
            departure_time = attributes.get('departure_time', None)
            departure_uncertainty = attributes.get('departure_uncertainty', None)
            direction_id = attributes.get('direction_id', None)
            last_trip = attributes.get('last_trip', None)
            revenue = attributes.get('revenue', None)
            schedule_relationship = attributes.get('schedule_relationship', None)
            status = attributes.get('status', None)
            stop_sequence = attributes.get('stop_sequence', None)
            update_type = attributes.get('update_type', None)
            
            # Extract route, trip, stop, and vehicle information from relationships
            route_id = None
            trip_id = None
            stop_id = None
            vehicle_id = None
            
            # Extract route ID
            if 'route' in relationships and relationships['route'].get('data'):
                route_id = relationships['route']['data'].get('id')
            
            # Extract trip ID  
            if 'trip' in relationships and relationships['trip'].get('data'):
                trip_id = relationships['trip']['data'].get('id')
                
            # Extract stop ID
            if 'stop' in relationships and relationships['stop'].get('data'):
                stop_id = relationships['stop']['data'].get('id')
                
            # Extract vehicle ID
            if 'vehicle' in relationships and relationships['vehicle'].get('data'):
                vehicle_id = relationships['vehicle']['data'].get('id')
            
            # Record metadata about ingestion
            current_datetime = datetime.datetime.now()
            ingestion_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
            ingestion_source = os.path.basename(__file__) if '__file__' in globals() else 'ingestion_schedules.py'
            
            # Create standardized prediction record
            standardized_schedules.append({
                'prediction_id': prediction_id,
                'arrival_time': arrival_time,
                'arrival_uncertainty': arrival_uncertainty,
                'departure_time': departure_time,
                'departure_uncertainty': departure_uncertainty,
                'direction_id': direction_id,
                'last_trip': last_trip,
                'revenue': revenue,
                'schedule_relationship': schedule_relationship,
                'status': status,
                'stop_sequence': stop_sequence,
                'update_type': update_type,
                'route_id': route_id,
                'trip_id': trip_id,
                'stop_id': stop_id,
                'vehicle_id': vehicle_id,
                'ingestion_datetime': ingestion_datetime,
                'ingestion_source': ingestion_source
            })

    else:
        # No schedules found in the response
        print("No current schedules.")
else:
    # The API request failed; print the HTTP status code
    print(f"Error: {response.status_code}")

# Convert the list of prediction dictionaries into a pandas DataFrame
output = pandas.DataFrame(standardized_schedules)

# Define BigQuery project, dataset, and table
project_id = 'mbta-reliability-analytics'
dataset_id = 'staging'
table_id = 'schedules_raw'

# Upload the DataFrame to BigQuery (replace table if it already exists)
to_gbq(output, f'{dataset_id}.{table_id}', project_id=project_id, if_exists='replace')

# Print number of uploaded rows
print(f"{len(output)} rows uploaded to BigQuery.")