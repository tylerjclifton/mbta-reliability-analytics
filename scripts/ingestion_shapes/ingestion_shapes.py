# Import standard libraries
import datetime
import os

# Import third party libraries
import pandas
import requests
from pandas_gbq import to_gbq

# Make a GET request to the MBTA alerts API
response = requests.get('https://api-v3.mbta.com/shapes?filter[route_type]=0')

# Check if the request was successful (HTTP status 200)
if response.status_code == 200:

    # Convert the response JSON into a Python dictionary
    data = response.json()

    # Extract the list of alerts from the response
    alerts = data['data']

    print(alerts)