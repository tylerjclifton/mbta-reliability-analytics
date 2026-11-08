"""
Tests for the shared ingest helpers in ingest/common/: run.py (failure
reports), fetch.py, load.py (append to bronze), and mbta_api.py.
"""

# Import standard libraries
import json
import sys
from types import SimpleNamespace

# Import third party libraries
import pandas as pd
import pytest

# Import the shared ingest helpers under test
from common import fetch, load, mbta_api, run

# ── Failure reports (the alerting contract in infra/monitoring.tf) ────────────

def last_report(capsys):
    """The structured failure report a job printed to stdout."""
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_fail_on_final_attempt_reports_job_failed(monkeypatch, capsys):
    monkeypatch.setenv('CLOUD_RUN_TASK_ATTEMPT', '1')
    monkeypatch.setenv('MAX_RETRIES', '1')

    with pytest.raises(SystemExit):
        run.fail('Request to https://example.test returned HTTP 503')

    report = last_report(capsys)
    assert report['severity'] == 'ERROR'
    assert report['event'] == 'job_failed'
    assert report['job'].startswith('ingest-')
    assert report['message'] == 'Request to https://example.test returned HTTP 503'


def test_fail_before_a_retry_only_warns(monkeypatch, capsys):
    """Cloud Run will retry, so this attempt must not trigger an alert email."""
    monkeypatch.setenv('CLOUD_RUN_TASK_ATTEMPT', '0')
    monkeypatch.setenv('MAX_RETRIES', '1')

    with pytest.raises(SystemExit):
        run.fail('Request to https://example.test returned HTTP 503')

    report = last_report(capsys)
    assert report['severity'] == 'WARNING'
    assert report['event'] == 'attempt_failed'


def test_uncaught_exception_reports_traceback(monkeypatch, capsys):
    monkeypatch.setattr(run.sys, '__excepthook__', lambda *args: None)
    try:
        {}['data']
    except KeyError as error:
        sys.excepthook(type(error), error, error.__traceback__)

    report = last_report(capsys)
    assert report['event'] == 'job_failed'
    assert report['message'].startswith("KeyError: 'data'")
    assert 'Traceback (most recent call last)' in report['message']


# ── Fetch (common/fetch.py) ───────────────────────────────────────────────────

def test_fetch_reports_an_http_error_with_its_reason(monkeypatch, capsys):
    body = '{"errors": [{"status": "429",\n "detail": "Rate limit exceeded"}]}'
    monkeypatch.setattr(fetch.requests, 'get', lambda *a, **k: SimpleNamespace(status_code=429, text=body))

    with pytest.raises(SystemExit) as exit_info:
        fetch.fetch('https://example.test')

    assert exit_info.value.code == 1
    assert last_report(capsys)['message'] == (
        'Request to https://example.test returned HTTP 429: '
        '{"errors": [{"status": "429", "detail": "Rate limit exceeded"}]}'
    )


def test_fetch_reports_a_network_error(monkeypatch, capsys):
    def refuse_connection(*args, **kwargs):
        raise fetch.requests.exceptions.ConnectionError('connection refused')

    monkeypatch.setattr(fetch.requests, 'get', refuse_connection)

    with pytest.raises(SystemExit):
        fetch.fetch('https://example.test')

    assert 'connection refused' in last_report(capsys)['message']


# ── Load (common/load.py) ─────────────────────────────────────────────────────

class FakeClient:
    """Records the BigQuery load instead of running it."""

    loads = []

    def __init__(self, project=None):
        pass

    def get_table(self, table_ref):
        return SimpleNamespace(schema=[load.bigquery.SchemaField('alert_id', 'STRING')])

    def load_table_from_dataframe(self, df, table_ref, job_config):
        FakeClient.loads.append(SimpleNamespace(df=df, table_ref=table_ref, job_config=job_config))
        return SimpleNamespace(result=lambda: None)


@pytest.fixture
def fake_bigquery(monkeypatch):
    """Swap BigQuery for FakeClient with a fixed target table; returns the recorded loads."""
    FakeClient.loads = []
    monkeypatch.setattr(load.bigquery, 'Client', FakeClient)
    monkeypatch.setenv('GCP_PROJECT_ID', 'proj')
    monkeypatch.setenv('BQ_DATASET_ID', 'bronze')
    monkeypatch.setenv('BQ_TABLE_ID', 'mbta_stops')
    return FakeClient.loads


def test_append_adds_audit_columns_and_appends(fake_bigquery):
    load.append_to_bronze(pd.DataFrame({'alert_id': ['1', '2']}))

    load_job = fake_bigquery[0]
    assert load_job.table_ref == 'proj.bronze.mbta_stops'
    assert load_job.job_config.write_disposition == 'WRITE_APPEND'
    # Every row in a run shares one timestamp — silver depends on it
    assert load_job.df['ingested_at'].nunique() == 1
    assert load_job.df['ingested_at'].iloc[0] == run.RUN_STARTED_AT
    assert load_job.df['ingested_by'].str.startswith('ingest-').all()


def test_append_loads_against_the_live_table_schema(fake_bigquery):
    load.append_to_bronze(pd.DataFrame({'alert_id': ['1']}))

    assert [field.name for field in fake_bigquery[0].job_config.schema] == ['alert_id']


def test_append_defaults_to_dev_bronze(fake_bigquery, monkeypatch):
    """Without BQ_DATASET_ID (a local run), rows go to dev_bronze, never production (decision 0012)."""
    monkeypatch.delenv('BQ_DATASET_ID')

    load.append_to_bronze(pd.DataFrame({'alert_id': ['1']}))

    assert fake_bigquery[0].table_ref == 'proj.dev_bronze.mbta_stops'


def test_append_skips_empty_frames(fake_bigquery):
    load.append_to_bronze(pd.DataFrame())

    assert fake_bigquery == []


def test_append_reports_a_failed_load(fake_bigquery, monkeypatch, capsys):
    def reject(self, df, table_ref, job_config):
        raise ValueError('bq_schema contains fields not present in dataframe')

    monkeypatch.setattr(FakeClient, 'load_table_from_dataframe', reject)

    with pytest.raises(SystemExit):
        load.append_to_bronze(pd.DataFrame({'alert_id': ['1']}))

    assert last_report(capsys)['message'] == (
        'BigQuery load into proj.bronze.mbta_stops failed: bq_schema contains fields not present in dataframe'
    )


# ── MBTA API settings (common/mbta_api.py) ────────────────────────────────────

def test_api_headers_carry_the_key_when_set(monkeypatch):
    monkeypatch.setenv('MBTA_API_KEY', 'test-key')

    assert mbta_api.api_headers() == {'x-api-key': 'test-key'}


def test_api_headers_without_a_key_are_empty(monkeypatch):
    monkeypatch.delenv('MBTA_API_KEY', raising=False)

    assert mbta_api.api_headers() == {}


def test_api_key_stays_out_of_failure_reports(monkeypatch, capsys):
    """A real connection error (nothing listens on this port) quotes the URL; the report is emailed."""
    monkeypatch.setenv('MBTA_API_KEY', 'test-key')

    with pytest.raises(SystemExit):
        fetch.fetch('http://127.0.0.1:9/alerts', params={'filter[activity]': 'ALL'},
                    headers=mbta_api.api_headers(), timeout=1)

    report = last_report(capsys)
    assert 'filter%5Bactivity%5D=ALL' in report['message']  # the query string is quoted...
    assert 'test-key' not in report['message']              # ...and the key isn't in it
