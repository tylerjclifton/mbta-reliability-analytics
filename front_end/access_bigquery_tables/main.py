import functions_framework
from google.cloud import bigquery
import json
from flask import jsonify

# Initialize BigQuery client
client = bigquery.Client()

@functions_framework.http
def mbta_api(request):
    """HTTP Cloud Function to serve MBTA alert data from BigQuery"""
    
    # Enable CORS for Netlify frontend
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)
    
    headers = {
        'Access-Control-Allow-Origin': '*'
    }
    
    # Get the endpoint from query parameter
    endpoint = request.args.get('endpoint', 'alerts')
    
    try:
        if endpoint == 'alerts':
            # Query gold alerts table
            query = """
                SELECT 
                    alert_id,
                    alert_start_date,
                    alert_end_date,
                    route_id,
                    route_name,
                    route_color,
                    stop_id,
                    stop_name,
                    stop_latitude,
                    stop_longitude,
                    alert_header,
                    alert_description,
                    alert_cause,
                    alert_effect,
                    alert_severity,
                    alert_created_at
                FROM `mbta-reliability-analytics.alerts.gold`
                WHERE alert_end_date >= CURRENT_DATE()
                   OR alert_end_date IS NULL
                ORDER BY alert_severity DESC, alert_created_at DESC
            """
            
        elif endpoint == 'shapes':
            # Query shapes table
            query = """
                SELECT 
                    shape_id,
                    polyline
                FROM `mbta-reliability-analytics.shapes.gold`
            """
            
        else:
            return (jsonify({'error': 'Invalid endpoint'}), 400, headers)
        
        # Execute query
        query_job = client.query(query)
        results = query_job.result()
        
        # Convert to list of dicts
        data = []
        for row in results:
            data.append(dict(row))
        
        return (jsonify(data), 200, headers)
        
    except Exception as e:
        return (jsonify({'error': str(e)}), 500, headers)