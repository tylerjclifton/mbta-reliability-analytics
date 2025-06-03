import requests
import datetime
import pandas as pd
from pandas_gbq import to_gbq
import os

# API endpoint for Red Line alerts
response = requests.get('https://api-v3.mbta.com/routes')
data = response.json

print(data)