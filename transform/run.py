"""
Transform job entrypoint (Dockerfile CMD)

Runs, in order, stopping at the first failure:
  1. `dbt build` — models + data and unit tests in DAG order; a failing test
     skips everything downstream of it, so bad data never reaches gold
  2. `dbt source freshness` — fails the run if an ingest job has stopped
     writing to bronze (thresholds in models/bronze/_bronze__sources.yml)
Both use the gcp target (attached service account, no keyfile) unless
DBT_TARGET says otherwise — e.g. DBT_TARGET=local to try it against the dev
datasets.

dbt's output streams to the job's logs unchanged. On failure, the job also logs
one structured failure report holding dbt's failure summary — which models,
tests, or sources failed and why — which the transform's alerting policy emails
(contract: infra/monitoring.tf). Checks at warn severity don't fail the run;
the ones that fired in a step that passed are logged as one warning report,
which emails at most once a day.
"""

# Import standard libraries
import json
import os
import pathlib
import re
import subprocess
import sys

TARGET = os.getenv('DBT_TARGET', 'gcp')

# Step name → its command, and the results file it writes (a dbt artifact),
# read for the checks that warned
STEPS = {
    'dbt build': (
        ['dbt', 'build', '--profiles-dir', '.', '--target', TARGET],
        pathlib.Path('target/run_results.json'),
    ),
    'dbt source freshness': (
        ['dbt', 'source', 'freshness', '--profiles-dir', '.', '--target', TARGET],
        pathlib.Path('target/sources.json'),
    ),
}

# Lines of dbt output kept in a failure report (the email shows them verbatim)
MAX_DETAIL_LINES = 40

# dbt prefixes most lines with a timestamp, e.g. "01:36:39  " (some lines are
# only a timestamp)
TIMESTAMP = re.compile(r'^\d{2}:\d{2}:\d{2}\s*')


def run(command):
    """Run a dbt command, streaming its output; return (exit code, output lines)."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, 'DBT_USE_COLORS': 'false'},  # plain text for logs and email
    )
    lines = []
    for line in process.stdout:
        print(line, end='', flush=True)
        lines.append(TIMESTAMP.sub('', line.rstrip()))
    return process.wait(), lines


def failure_details(lines):
    """
    The part of dbt's output that says what failed:
      - `dbt build` with failing nodes: its closing summary ("Completed with
        N errors…" followed by each failure and its compiled SQL path)
      - a dbt crash (auth, compilation): everything from "Encountered an error"
      - `dbt source freshness`: each source that is stale or errored
    Falls back to the last lines of output.
    """
    for marker in ('Completed with', 'Encountered an error'):
        starts = [i for i, line in enumerate(lines) if marker in line]
        if starts:
            details = lines[starts[-1]:]
            break
    else:
        details = [line for line in lines if 'ERROR' in line] or lines

    details = [line for line in details if line.strip()]
    return '\n'.join(details[-MAX_DETAIL_LINES:])


def warnings_in(results_file):
    """
    One line per check that warned, from a step's results file: a data test
    (run_results.json) or a source loaded longer ago than its warn_after
    (sources.json).
    """
    lines = []
    for result in json.loads(results_file.read_text())['results']:
        if result['status'] != 'warn':
            continue
        # unique_id is "<type>.<project>.<name>[.<hash>]", with "<source>.<table>" for a source
        kind, _, *name = result['unique_id'].split('.')
        if kind == 'source':
            count, period = result['criteria']['warn_after']['count'], result['criteria']['warn_after']['period']
            loaded_at = result['max_loaded_at'][:16].replace('T', ' ')
            lines.append(f"source {'.'.join(name[:2])}: last loaded {loaded_at} UTC, "
                         f"warns after {count} {period}{'s' if count != 1 else ''}")
        else:
            lines.append(f"{kind} {name[0]}: {result['message']}")
    return lines


def report_warnings(warnings):
    """
    Log the checks that warned as one structured entry, per the contract in
    infra/monitoring.tf; nothing if none did.
    """
    if warnings:
        print(json.dumps({
            'severity': 'WARNING',
            'event':    'job_warned',
            'job':      'transform',
            'message':  '\n'.join(warnings),
        }), flush=True)


def report_failure(summary, details):
    """
    Log the failure as one structured entry, per the contract in
    infra/monitoring.tf (as ingest/common/run.py does). The transform never
    retries (MAX_RETRIES = 0), so every failure is final and emails an alert.
    """
    is_final_attempt = int(os.getenv('CLOUD_RUN_TASK_ATTEMPT', '0')) >= int(os.getenv('MAX_RETRIES', '0'))
    print(json.dumps({
        'severity': 'ERROR' if is_final_attempt else 'WARNING',
        'event':    'job_failed' if is_final_attempt else 'attempt_failed',
        'job':      'transform',
        'message':  f'{summary}\n\n{details}'.strip(),
    }), flush=True)


if __name__ == '__main__':
    warnings = []
    for step, (command, results_file) in STEPS.items():
        # A crashed step writes no results, so clear any left by an earlier run
        results_file.unlink(missing_ok=True)
        exit_code, output = run(command)
        if exit_code != 0:
            # A failed step's own warnings are in its failure summary
            report_warnings(warnings)
            report_failure(f'`{step}` failed (exit code {exit_code})', failure_details(output))
            sys.exit(exit_code)
        warnings += warnings_in(results_file)
    report_warnings(warnings)
