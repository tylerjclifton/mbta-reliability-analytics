# Import standard libraries
import datetime
import logging
import os

# Import third party libraries
import pandas
import requests
from google.cloud import bigquery

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize BigQuery client
client = bigquery.Client()

# NWS station and historical observations endpoint
STATION_ID = 'KBOS'
NWS_OBSERVATIONS_URL = f'https://api.weather.gov/stations/{STATION_ID}/observations'
NWS_HEADERS = {
    'User-Agent': '(MBTA Reliability Analytics, tyler@example.com)',
    'Accept': 'application/json'
}

# Pull all observations for yesterday (complete day)
yesterday   = datetime.date.today() - datetime.timedelta(days=1)
start_utc   = f"{yesterday}T00:00:00Z"
end_utc     = f"{yesterday}T23:59:59Z"

logging.info(f"Fetching NWS observations for {yesterday}")

# Fetch all observations for the day with pagination support
all_observations = []
url    = NWS_OBSERVATIONS_URL
params = {'start': start_utc, 'end': end_utc, 'limit': 500}

while url:
    try:
        response = requests.get(url, params=params, headers=NWS_HEADERS, timeout=30)
    except requests.exceptions.Timeout:
        logging.error("Request timed out")
        exit(1)

    if response.status_code != 200:
        logging.error(f"API request failed with status code: {response.status_code}")
        exit(1)

    data     = response.json()
    features = data.get('features', [])
    all_observations.extend(features)

    # NWS paginates via a next link in the response
    next_url = data.get('pagination', {}).get('next')
    # Stop paginating if the last feature's date is before yesterday
    if features and next_url:
        last_ts = features[-1].get('properties', {}).get('timestamp', '')
        if last_ts and last_ts[:10] < str(yesterday):
            next_url = None
    url    = next_url
    params = {}  # Params are embedded in the next URL

logging.info(f"Fetched {len(all_observations)} raw observations")

if not all_observations:
    logging.info(f"No observations available for {yesterday} yet")
    exit(0)

# Extract fields from each observation
records = []
for feature in all_observations:
    props = feature.get('properties', {})

    ts_raw = props.get('timestamp')
    if not ts_raw:
        continue
    ts = datetime.datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))

    # Guard: skip any observations outside yesterday's date (can occur if
    # pagination follows next URLs that don't preserve the date bounds)
    if ts.date() != yesterday:
        continue

    def get_value(key):
        return props.get(key, {}).get('value') if isinstance(props.get(key), dict) else None

    temp_c  = get_value('temperature')
    temp_f  = (temp_c * 9 / 5) + 32 if temp_c is not None else None
    wind_ms = get_value('windSpeed')
    wind_mph = wind_ms * 0.621371 if wind_ms is not None else None  # km/h → mph
    precip_mm   = get_value('precipitationLastHour')
    humidity    = get_value('relativeHumidity')
    vis_m       = get_value('visibility')
    vis_miles   = vis_m * 0.000621371 if vis_m is not None else None

    records.append({
        'timestamp':        ts,
        'hour':             ts.hour,
        'temperature_f':    temp_f,
        'wind_speed_mph':   wind_mph,
        'precipitation_mm': precip_mm,
        'humidity_percent': humidity,
        'visibility_miles': vis_miles,
    })

df = pandas.DataFrame(records)

if df.empty:
    logging.info("No usable observations after extraction")
    exit(0)

# Deduplicate to one observation per hour — this ensures each hour contributes
# equally to daily averages, preventing stormy hours (many SPECI reports) from
# being over-represented vs clear hours (one METAR per hour)
df_hourly = (
    df.sort_values('timestamp')
    .drop_duplicates(subset=['hour'], keep='first')
)

# Aggregate to single daily row using hourly-deduplicated observations
ingestion_timestamp = datetime.datetime.now(datetime.timezone.utc)
daily = {
    'observation_date':      yesterday,
    'station_id':            STATION_ID,
    'avg_temperature_f':     round(float(df_hourly['temperature_f'].dropna().mean()), 2)   if df_hourly['temperature_f'].notna().any() else None,
    'max_temperature_f':     round(float(df_hourly['temperature_f'].dropna().max()), 2)    if df_hourly['temperature_f'].notna().any() else None,
    'total_precipitation_mm':round(float(df_hourly['precipitation_mm'].fillna(0).sum()), 2),
    'avg_wind_speed_mph':    round(float(df_hourly['wind_speed_mph'].dropna().mean()), 2)  if df_hourly['wind_speed_mph'].notna().any() else None,
    'avg_humidity_percent':  round(float(df_hourly['humidity_percent'].dropna().mean()), 2) if df_hourly['humidity_percent'].notna().any() else None,
    'min_visibility_miles':  round(float(df_hourly['visibility_miles'].dropna().min()), 2) if df_hourly['visibility_miles'].notna().any() else None,
    'ingestion_source':      'ingest-nws-weather',
    'ingestion_timestamp':   ingestion_timestamp,
}

output = pandas.DataFrame([daily])

# Define BigQuery project, dataset, and table using environment variables
project_id = os.getenv('BQ_PROJECT_ID', 'mbta-reliability-analytics')
dataset_id = os.getenv('BQ_DATASET_ID', 'stage')
table_id   = os.getenv('BQ_TABLE_ID', 'nws_weather')

# Schema for the daily aggregated weather table
schema = [
    bigquery.SchemaField("observation_date",       "DATE"),
    bigquery.SchemaField("station_id",             "STRING"),
    bigquery.SchemaField("avg_temperature_f",      "FLOAT"),
    bigquery.SchemaField("max_temperature_f",      "FLOAT"),
    bigquery.SchemaField("total_precipitation_mm", "FLOAT"),
    bigquery.SchemaField("avg_wind_speed_mph",     "FLOAT"),
    bigquery.SchemaField("avg_humidity_percent",   "FLOAT"),
    bigquery.SchemaField("min_visibility_miles",   "FLOAT"),
    bigquery.SchemaField("ingestion_source",       "STRING"),
    bigquery.SchemaField("ingestion_timestamp",    "TIMESTAMP"),
]

# Write to BigQuery — WRITE_TRUNCATE replaces staging with today's single daily row
try:
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    load_job = client.load_table_from_dataframe(
        output,
        f"{project_id}.{dataset_id}.{table_id}",
        job_config=job_config
    )
    load_job.result()
    logging.info(f"Uploaded daily weather record for {yesterday} to BigQuery")
except Exception as e:
    logging.error(f"BigQuery upload failed: {e}")
    exit(1)
