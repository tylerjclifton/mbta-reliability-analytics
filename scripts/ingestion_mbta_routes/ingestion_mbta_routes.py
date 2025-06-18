# imports
import requests
import datetime
import pandas as pd
from pandas_gbq import to_gbq
import os

response = requests.get('https://api-v3.mbta.com/routes') # makes api call to mbta routes

if response.status_code == 200: # checks to see if request was succesful
    data = response.json() # converts response into python dictionary
    routes = data['data']

    if routes:
        standardized_routes = []

        for route in routes:
            # id
            route_id = route.get('id', 'No id')

            # type
            # route_type = route.get('type','No type') -- is always 'route' so don't need

            # attributes
            route_attributes = route.get('attributes', {})
            route_color = route_attributes.get('color', 'No color')
            route_description = route_attributes.get('description', 'No description')

            # direction destinations
            route_direction_destinations = route_attributes.get('direction_destinations', [])
            route_direction_destination_1 = route_direction_destinations[0] if len(route_direction_destinations) > 0 else "Unknown direction destination"
            route_direction_destination_2 = route_direction_destinations[1] if len(route_direction_destinations) > 1 else "Unknown direction destination"

            # direction names
            route_direction_names = route_attributes.get('direction_names', [])
            route_direction_name_1 = route_direction_names[0] if len(route_direction_names) > 0 else "Unknown destination name"
            route_direction_name_2 = route_direction_names[1] if len(route_direction_names) > 1 else "Unknown destination name"

            route_fare_class = route_attributes.get('fare_class', 'No fare class')
            route_long_name = route_attributes.get('long_name', 'No long name')
            route_short_name = route_attributes.get('short_name', 'No short name')
            route_sort_order = route_attributes.get('sort_order', 'No sort order')
            route_text_color = route_attributes.get('text_color', 'No text color')
            route_type = route_attributes.get('type', 'No type')

            # links
            route_links = route.get('links', {}).get('self', 'No link')
            
            # relationships
            route_relationships = route.get('relationships', {}).get('agency', {}).get('data', {})
            route_agency_id = route_relationships.get('id')
            route_agency_type = route_relationships.get('type')

            # line
            route_line = route.get('line', {}).get('data', {})
            route_line_id = route_line.get('id')
            route_line_type = route_line.get('type')

            standardized_routes.append({
                'route_id': route_id,
                'route_color': route_color,
                'route_description': route_description,
                'route_direction_destination_1': route_direction_destination_1,
                'route_direction_destination_2': route_direction_destination_2,
                'route_direction_name_1': route_direction_name_1,
                'route_direction_name_2': route_direction_name_2,
                'route_fare_class': route_fare_class,
                'route_long_name': route_long_name,
                'route_short_name': route_short_name,
                'route_sort_order': route_sort_order,
                'route_text_color': route_text_color,
                'route_links': route_links,
                'route_agency_id': route_agency_id,
                'route_agency_type': route_agency_type,
                'route_line_id': route_line_id,
                'route_line_type': route_line_type,
            })

    else:
        print("No routes found.")

output = pd.DataFrame(standardized_routes)

# Upload to BigQuery
project_id = 'sonic-earth-456400-s3'
dataset_id = 'mbta'
table_id = 'external_routes'

# Upload DataFrame to BigQuery (if table doesn't exist, it will be created)
to_gbq(output, f'{dataset_id}.{table_id}', project_id=project_id, if_exists='replace')

print(f"{len(output)} rows uploaded to BigQuery.")