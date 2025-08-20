# Import standard libraries
import datetime
import os

# Import third party libraries
import pandas
import requests
from pandas_gbq import to_gbq

# Make a GET request to the MBTA routes API
response = requests.get('https://api-v3.mbta.com/routes')

# Check if the request was successful (HTTP status 200)
if response.status_code == 200:

    # Convert the response JSON into a Python dictionary
    data = response.json()

    # Extract the list of routes from the response
    routes = data['data']

    # Proceed only if there are any routes
    if routes:
        standardized_routes = []

        # Loop through each route in the list
        for route in routes:

            # Safely extract the alert ID and its attributes dictionary
            route_id = route.get('id', 'No route id')
            attributes = route.get('attributes', {})

            # Extract specific route details from the attributes dictionary
            color = attributes.get('color', 'No color')
            description = attributes.get('description', 'No description')
            direction_destinations = attributes.get('direction_destinations', [])
            direction_destination_1 = direction_destinations[0] if len(direction_destinations) > 0 else "Unknown direction destination"
            direction_destination_2 = direction_destinations[1] if len(direction_destinations) > 1 else "Unknown direction destination"
            direction_names = attributes.get('direction_names', [])
            direction_name_1 = direction_names[0] if len(direction_names) > 0 else "Unknown destination name"
            direction_name_2 = direction_names[1] if len(direction_names) > 1 else "Unknown destination name"
            fare_class = attributes.get('fare_class', 'No fare class')
            long_name = attributes.get('long_name', 'No long name')
            short_name = attributes.get('short_name', 'No short name')
            text_color = attributes.get('text_color', 'No text color')
            type = attributes.get('type', 'No type')

            # Record metadata about ingestion
            current_datetime = datetime.datetime.now()
            ingestion_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
            ingestion_source = os.path.basename(__file__) if '__file__' in globals() else 'mbta_routes_ingestion.py'

            # Append route to standardized routes list
            standardized_routes.append({
                'route_id': route_id,
                'color': color,
                'description': description,
                'direction_destination_1': direction_destination_1,
                'direction_destination_2': direction_destination_2,
                'direction_name_1': direction_name_1,
                'direction_name_2': direction_name_2,
                'fare_class': fare_class,
                'long_name': long_name,
                'short_name': short_name,
                'text_color': text_color,
                'type': type,
                'ingestion_datetime': ingestion_datetime,
                'ingestion_source': ingestion_source
            })

    else:
        # No routes found in the response
        print("No routes found.")

else:
    # The API request failed; print the HTTP status code
    print(f"Error: {response.status_code}")

# Convert the list of route dictionaries into a pandas DataFrame
output = pandas.DataFrame(standardized_routes)

# Define BigQuery project, dataset, and table
project_id = 'mbta-reliability-analytics'
dataset_id = 'staging'
table_id = 'routes'

# Upload the DataFrame to BigQuery (replace table if it already exists)
to_gbq(output, f'{dataset_id}.{table_id}', project_id=project_id, if_exists='replace')

# Print number of uploaded rows
print(f"{len(output)} rows uploaded to BigQuery.")