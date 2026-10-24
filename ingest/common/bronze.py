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
    replaced by "_" (e.g. ingest/mbta-stops → bronze.mbta_stops). A job whose
    table is named otherwise passes table_id (mbta-alerts writes
    bronze.mbta_alerts_raw).
  - Bronze is append-only: jobs never update or delete rows.
  - A job that fails — through fail() or an uncaught exception — logs one
    structured failure report (report_failure()), which the job's alerting
    policy emails (infra/monitoring.tf).
"""

# Import standard libraries
import datetime
import json
import logging
import os
import sys
import traceback

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


def report_failure(summary, details=''):
    """
    Log this run's failure as one structured entry (contract: infra/monitoring.tf).

    Cloud Run reads a JSON line on stdout as a structured log entry. Only the
    task's final attempt reports event "job_failed" at ERROR, which emails an
    alert; an attempt Cloud Run will retry logs "attempt_failed" at WARNING, so
    a transient error the retry absorbs sends nothing. CLOUD_RUN_TASK_ATTEMPT
    (0-based) is set by Cloud Run; MAX_RETRIES by Terraform.
    """
    is_final_attempt = int(os.getenv('CLOUD_RUN_TASK_ATTEMPT', '0')) >= int(os.getenv('MAX_RETRIES', '0'))
    print(json.dumps({
        'severity': 'ERROR' if is_final_attempt else 'WARNING',
        'event':    'job_failed' if is_final_attempt else 'attempt_failed',
        'job':      f"ingest-{JOB_NAME}",
        'message':  f"{summary}\n\n{details}".strip(),
    }), flush=True)


def fail(message):
    """Report a failure and exit non-zero so Cloud Run marks the execution failed."""
    report_failure(message)
    sys.exit(1)


def _report_uncaught_exception(exc_type, exc_value, exc_traceback):
    """Report any exception a job didn't handle, with its traceback, then exit as usual."""
    details = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    report_failure(f"{exc_type.__name__}: {exc_value}", details)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


# Every job imports this module, so this covers unexpected errors in any job
# (a changed API response, a shaping bug) as well as the fail() paths
sys.excepthook = _report_uncaught_exception


def fetch(url, params=None, headers=None, timeout=60):
    """GET a URL, exiting the job on a network error or non-200 response."""
    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as error:
        fail(f"Request to {url} failed: {error}")

    if response.status_code != 200:
        fail(f"Request to {url} returned HTTP {response.status_code}")

    return response


def append_to_bronze(df: pandas.DataFrame, table_id=None):
    """
    Append a DataFrame to a bronze table, adding the audit columns.

    The target comes from BQ_PROJECT_ID / BQ_DATASET_ID / BQ_TABLE_ID (set by
    Terraform), falling back to the naming convention for local runs. Pass
    table_id to write a table other than the job's own, in the same dataset.
    """
    if df.empty:
        logging.info("No rows to write")
        return

    # Resolve the target table
    project_id = os.getenv('BQ_PROJECT_ID', 'mbta-reliability-analytics')
    dataset_id = os.getenv('BQ_DATASET_ID', 'bronze')
    table_id   = table_id or os.getenv('BQ_TABLE_ID', JOB_NAME.replace('-', '_'))
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
