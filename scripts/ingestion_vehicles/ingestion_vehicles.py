# Import standard libraries
import datetime
import os

# Import third party libraries
import pandas
import requests
from pandas_gbq import to_gbq

# Set routes to pull vehicles for
routes = ['Red', 'Orange', 'Blue']

# Initialize the list at the top level
standardized_vehicles = []

# Make a GET request to the MBTA vehicles API
response = requests.get('https://api-v3.mbta.com/vehicles',
                        params={'filter[route]': routes, 'page[limit]': '500'})

# Check if the request was successful (HTTP status 200)
if response.status_code == 200:

    # Convert the response JSON into a Python dictionary
    data = response.json()

    # Extract the list of vehicles from the response
    vehicles = data['data']

    # Proceed only if there are any vehicles
    if vehicles:

        # Loop through each vehicle in the list
        for vehicle in vehicles:

            # Safely extract the vehicle ID, attributes dictionary, and relationships object
            vehicle_id = vehicle.get('id', 'No vehicle ID')
            attributes = vehicle.get('attributes', {})
            relationships = vehicle.get('relationships', {})

            # Extract specific details from the attributes dictionary
            label = attributes.get('label', None)
            latitude = attributes.get('latitude', None)
            longitude = attributes.get('longitude', None)
            bearing = attributes.get('bearing', None)
            speed = attributes.get('speed', None)
            current_status = attributes.get('current_status', None)
            current_stop_sequence = attributes.get('current_stop_sequence', None)
            direction_id = attributes.get('direction_id', None)
            occupancy_status = attributes.get('occupancy_status', None)
            updated_at = attributes.get('updated_at', None)

            # Extract route, trip, and stop information from relationships
            route_id = None
            trip_id = None
            stop_id = None

            if 'route' in relationships and relationships['route'].get('data'):
                route_id = relationships['route']['data'].get('id')

            if 'trip' in relationships and relationships['trip'].get('data'):
                trip_id = relationships['trip']['data'].get('id')

            if 'stop' in relationships and relationships['stop'].get('data'):
                stop_id = relationships['stop']['data'].get('id')

            # Record metadata about ingestion
            current_datetime = datetime.datetime.now()
            ingestion_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
            ingestion_source = os.path.basename(__file__) if '__file__' in globals() else 'ingestion_vehicles.py'

            # Create standardized vehicle record
            standardized_vehicles.append({
                'vehicle_id': vehicle_id,
                'label': label,
                'latitude': latitude,
                'longitude': longitude,
                'bearing': bearing,
                'speed': speed,
                'current_status': current_status,
                'current_stop_sequence': current_stop_sequence,
                'direction_id': direction_id,
                'occupancy_status': occupancy_status,
                'updated_at': updated_at,
                'route_id': route_id,
                'trip_id': trip_id,
                'stop_id': stop_id,
                'ingestion_datetime': ingestion_datetime,
                'ingestion_source': ingestion_source
            })

    else:
        # No vehicles found in the response
        print("No current vehicles.")
else:
    # The API request failed; print the HTTP status code
    print(f"Error: {response.status_code}")

# Convert the list of vehicle dictionaries into a pandas DataFrame
output = pandas.DataFrame(standardized_vehicles)

# Define BigQuery project, dataset, and table
project_id = 'mbta-reliability-analytics'
dataset_id = 'staging'
table_id = 'vehicles_raw'

# Upload the DataFrame to BigQuery (replace table if it already exists)
to_gbq(output, f'{dataset_id}.{table_id}', project_id=project_id, if_exists='replace')

# Print number of uploaded rows
print(f"{len(output)} rows uploaded to BigQuery.")