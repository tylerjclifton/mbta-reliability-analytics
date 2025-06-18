# imports
import requests
import datetime
import pandas as pd
from pandas_gbq import to_gbq
import os

response = requests.get('https://api-v3.mbta.com/routes') # makes api call to mbta routes

if response.status_code == 200: # checks to see if request was succesful
    routes = response.json() # converts response into python dictionary

    if routes:
        standardized_routes = []

    for route in routes:
        

        route_id = route.get('id', 'No id')
        route_attributes = route.get('attribute', {})

        color = route_attributes.get('color', 'No color available')
        description = route_attributes.get('description', 'No description available')
        direction_destination = route_attributes.get()
print(routes)