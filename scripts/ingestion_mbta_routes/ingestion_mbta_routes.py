import requests
import datetime
import pandas as pd
from pandas_gbq import to_gbq
import os

# API endpoint for Red Line alerts
response = requests.get('https://api-v3.mbta.com/routes')

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

            alert_header = alert_attributes.get('header', 'No header')
            alert_description = alert_attributes.get('description', 'No description')
            alert_active_period = alert_attributes.get('active_period', [])
            alert_cause = alert_attributes.get('cause', 'No cause')
            alert_effect = alert_attributes.get('effect', 'No effect')
            alert_severity = alert_attributes.get('severity', 'No severity')
            alert_lifecycle = alert_attributes.get('lifecycle', 'No lifecycle')

            if alert_active_period:
                period = alert_active_period[0]
                alert_start = datetime.datetime.fromisoformat(period.get('start')) if period.get('start') else None
                alert_end = datetime.datetime.fromisoformat(period.get('end')) if period.get('end') else None
            else:
                alert_start = None
                alert_end = None
            
            # Creates ingestion info fields
            current_datetime = datetime.datetime.now()
            ingestion_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S") #Format: Year-Month-Day Hour:Minute:Second
            ingestion_source = os.path.basename(__file__) if '__file__' in globals() else 'mbta_alerts_ingestion.py' #Gets file name
            
            # If routes are listed, create one row per route
            has_route = False
            for entity in alert_informed_entity:
                route = entity.get('route')
                if route:
                    has_route = True
                    standardized_alerts.append({
                        'alert_start': alert_start,
                        'alert_end': alert_end,
                        'route': route,
                        'id': alert_id,
                        'header': alert_header,
                        'description': alert_description,
                        'cause': alert_cause,
                        'effect': alert_effect,
                        'severity': alert_severity,
                        'lifecycle': alert_lifecycle,
                        'ingestion_datetime': ingestion_datetime,
                        'ingestion_source': ingestion_source
                    })
            
            # If no routes found, adds single row with 'No route'
            if not has_route:
                standardized_alerts.append({
                    'alert_start': alert_start,
                    'alert_end': alert_end,
                    'route': 'No route',
                    'id': alert_id,
                    'header': alert_header,
                    'description': alert_description,
                    'cause': alert_cause,
                    'effect': alert_effect,
                    'severity': alert_severity,
                    'lifecycle': alert_lifecycle,
                    'ingestion_datetime': ingestion_datetime,
                    'ingestion_source': ingestion_source
                })

    else:
        print("No current alerts.")
else:
    print(f"Error: {response.status_code}")

output = pd.DataFrame(standardized_alerts)

# Upload to BigQuery
project_id = 'sonic-earth-456400-s3'
dataset_id = 'mbta'
table_id = 'external_alerts'

# Upload DataFrame to BigQuery (if table doesn't exist, it will be created)
to_gbq(output, f'{dataset_id}.{table_id}', project_id=project_id, if_exists='replace')

print(f"{len(output)} rows uploaded to BigQuery.")