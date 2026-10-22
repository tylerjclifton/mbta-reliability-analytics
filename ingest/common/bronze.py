"""
Shared helpers for ingest jobs.

Every ingest job follows the same three steps:
  1. Fetch from its source              → fetch()
  2. Shape the response into a DataFrame whose columns match its bronze table
  3. Append the DataFrame to bronze     → append_to_bronze()

Bronze tables are defined in Terraform (infra/bigquery.tf). append_to_bronze()
loads against the live table's schema, so column names and types are owned in
that one place: a DataFrame with a missing or misnamed column fails the load
instead of silently creating a mismatched table.

Conventions:
  - A job lives in ingest/<job>/main.py and writes to bronze.<job> with "-"
    replaced by "_" (e.g. ingest/mbta-alerts → bronze.mbta_alerts).
  - Bronze is append-only: jobs never update or delete rows.
"""

# Import standard libraries
import datetime
import logging
import os
import sys

# Import third party libraries
import pandas
import requests
from google.cloud import bigquery

# Configure logging once for every job
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# One timestamp per run, stamped on every row the run writes. Silver relies on
# this: rows sharing the latest ingested_at are exactly the latest run's rows.
RUN_STARTED_AT = datetime.datetime.now(datetime.timezone.utc)

# Job name from the script's folder (e.g. "mbta-alerts"); drives the default
# bronze table name and the ingested_by audit value
JOB_NAME = os.path.basename(os.path.dirname(os.path.abspath(sys.argv[0])))


def fail(message):
    """Log an error and exit non-zero so Cloud Run marks the execution failed."""
    logging.error(message)
    sys.exit(1)


def fetch(url, params=None, headers=None, timeout=60):
    """GET a URL, exiting the job on a network error or non-200 response."""
    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as error:
        fail(f"Request to {url} failed: {error}")

    if response.status_code != 200:
        fail(f"Request to {url} returned HTTP {response.status_code}")

    return response


def append_to_bronze(df: pandas.DataFrame):
    """
    Append a DataFrame to this job's bronze table, adding the audit columns.

    The target comes from BQ_PROJECT_ID / BQ_DATASET_ID / BQ_TABLE_ID (set by
    Terraform), falling back to the naming convention for local runs.
    """
    if df.empty:
        logging.info("No rows to write")
        return

    # Resolve the target table
    project_id = os.getenv('BQ_PROJECT_ID', 'mbta-reliability-analytics')
    dataset_id = os.getenv('BQ_DATASET_ID', 'bronze')
    table_id   = os.getenv('BQ_TABLE_ID', JOB_NAME.replace('-', '_'))
    table_ref  = f"{project_id}.{dataset_id}.{table_id}"

    # Stamp the audit columns shared by every bronze table
    df = df.assign(ingested_at=RUN_STARTED_AT, ingested_by=f"ingest-{JOB_NAME}")

    # Load against the table's own schema (owned by Terraform) and append —
    # bronze is append-only, so earlier rows are never overwritten
    client = bigquery.Client(project=project_id)
    try:
        job_config = bigquery.LoadJobConfig(
            schema=client.get_table(table_ref).schema,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        client.load_table_from_dataframe(df, table_ref, job_config=job_config).result()
    except Exception as error:
        fail(f"BigQuery load into {table_ref} failed: {error}")

    logging.info(f"Appended {len(df)} rows to {table_ref}")
