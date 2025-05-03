import requests
import datetime
import pandas as pd
from pandas_gbq import to_gbq
import os

# API endpoint for Red Line alerts
response = requests.get('https://api-v3.mbta.com/alerts')

# Check if request was successful
if response.status_code == 200: # checks to see if request was succesful
    data = response.json() # converts response into Python dictionary
    alerts = data['data']

    if alerts:
        standardized_alerts = []

        for alert in alerts:
            alert_id = alert.get('id', 'No id')
            alert_attributes = alert.get('attributes', {})
            alert_informed_entity = alert_attributes.get('informed_entity', [])

            # Add all informed routes to the set
            unique_routes = set()
            for entity in alert_informed_entity:
                route = entity.get('route')
                if route:
                    unique_routes.add(route)
                if unique_routes:
                    sorted_routes = sorted(unique_routes)
                    routes = ", ".join(sorted_routes)
            else:
                route = 'No route'

            alert_header = alert_attributes.get('header', 'No header')
            alert_description = alert_attributes.get('description', 'No description')
            alert_active_period = alert_attributes.get('active_period', [])
            alert_cause = alert_attributes.get('cause', 'No cause')
            alert_effect = alert_attributes.get('effect', 'No effect')
            alert_severity = alert_attributes.get('severity', 'No severity')
            alert_lifecycle = alert_attributes.get('lifecycle', 'No lifecycle')

            for period in alert_active_period:
                start = period.get('start', 'No period start')
                end = period.get('end', 'No period end')
            
            # bronze level additions
            current_datetime = datetime.datetime.now()
            ingestion_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S") #Format: Year-Month-Day Hour:Minute:Second
            ingestion_source = os.path.basename(__file__) #Gets file name


            standardized_alerts.append({
                'routes':routes,
                'id':alert_id,
                'header':alert_header,
                'description':alert_description,
                'alert_start':start,
                'alert_end':end,
                'cause':alert_cause,
                'effect':alert_effect,
                'severity':alert_severity,
                'lifecycle':alert_lifecycle,
                'ingestion_datetime':ingestion_datetime,
                'ingestion_source':ingestion_source
            })
    else:
        print("No current alerts for the Red Line.")
else:
    print(f"Error: {response.status_code}")

output = pd.DataFrame(standardized_alerts)

# Upload to BigQuery
project_id = 'sonic-earth-456400-s3'
dataset_id = 'mbta'
table_id = 'external_mbta_alerts'

# Upload DataFrame to BigQuery (if table doesn't exist, it will be created)
to_gbq(output, f'{dataset_id}.{table_id}', project_id=project_id, if_exists='replace')

print('done')