"""
Shared fixtures for ingest job tests.

Each job is a script (ingest/<job>/main.py) that runs top to bottom: fetch →
shape → append_to_bronze(). `run_job` executes a script for real with the two
edges replaced — HTTP responses are canned, and the DataFrame handed to
append_to_bronze is captured instead of loaded into BigQuery.
"""

import json
import runpy
import sys
from pathlib import Path
from unittest import mock

import pytest

INGEST_DIR = Path(__file__).resolve().parents[1]


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, body, status_code=200):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body if isinstance(self._body, (dict, list)) else json.loads(self._body)

    @property
    def text(self):
        return self._body if isinstance(self._body, str) else json.dumps(self._body)


@pytest.fixture
def run_job(monkeypatch):
    """
    run_job(job, responses, table_id=None) → DataFrame passed to append_to_bronze (or None).

    `responses` is a list of bodies returned by successive HTTP GETs.
    `table_id` picks which write to return for a job that writes two tables:
    None is the job's own table, anything else the table_id it passed.
    """

    def _run(job, responses, table_id=None):
        import common.bronze as bronze

        bodies = iter(responses)
        captured = {}
        monkeypatch.setattr(bronze.requests, "get", lambda *a, **k: FakeResponse(next(bodies)))
        monkeypatch.setattr(bronze, "append_to_bronze",
                            lambda df, table_id=None: captured.setdefault(table_id, df))

        script = INGEST_DIR / job / "main.py"
        with mock.patch.object(sys, "argv", [str(script)]):
            runpy.run_path(str(script), run_name="__main__")
        return captured.get(table_id)

    return _run
