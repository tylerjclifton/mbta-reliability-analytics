# Runbook

How to do the occasional operational tasks. Every command assumes `gcloud` is signed in to `mbta-reliability-analytics` ([setup](setup.md)), and jobs run in `us-east1`.

## Check that alert emails work

Safe, and touches no data. It fails the yearly routes job on purpose: attempt 1 only warns, attempt 2 alerts, so it also exercises the retry logic. Verified end to end on 2026-10-23 (email from `alerting-noreply@google.com`).

```bash
gcloud run jobs execute ingest-mbta-routes --region us-east1 --wait \
  --args=-c,"import sys; sys.argv = ['mbta-routes/main.py']; from common import bronze; raise RuntimeError('TEST ALERT - deliberate failure; no data was touched')"
```

Don't put commas in the Python code, since `--args` splits on them. The email arrives within about a minute. The test leaves a failed execution in the job's history, which is expected.

## Run a job now

```bash
gcloud run jobs execute <job> --region us-east1 --wait   # ingest-mbta-alerts, ingest-mbta-stops, transform, …
```

## Backfill weather

NOAA revises recent days, so the job re-pulls a window. Widen it for a one-off backfill:

```bash
gcloud run jobs execute ingest-noaa-weather --region us-east1 --update-env-vars LOOKBACK_DAYS=800
```

## Rebuild an incremental silver table

`silver.mbta_alerts__by_route` and `silver.mbta_alerts__base` only read new snapshots each run. If their logic changes in a way that needs history reprocessed, rebuild them from bronze (cheap: a few MB):

```bash
cd transform
dbt build --profiles-dir . --target local --full-refresh --select <model>   # in dev_silver first
dbt build --profiles-dir . --target gcp   --full-refresh --select <model>   # then production silver
```

The second command runs with your own credentials against production silver. It rebuilds only that table from bronze, and bronze is never touched. The next hourly transform carries on incrementally from there.

## Rotate the MBTA API key

```bash
printf '%s' "<new key>" | gcloud secrets versions add mbta-api-key --data-file=-
```

Jobs read the `latest` version at their next run.

## Roll back a deploy

Re-run the GitHub Actions deploy for an earlier commit, or revert the commit and push. Artifact Registry keeps the 5 most recent images.

## Check what's deployed

Each deploy tags every image with its commit (the first 12 characters of the SHA), so the dashboard's image says which commit is live:

```bash
gcloud run services describe serve --region us-east1 --format="value(spec.template.spec.containers[0].image)"
# …/frontend/serve:42e675d0ce5c   → compare with: git log --oneline -3
```

To follow a CI run itself, use the Actions tab on GitHub or `gh run watch`. GitHub's API also answers without `gh`, but unauthenticated requests are limited to 60 an hour, so don't poll it in a loop:

```bash
curl -s "https://api.github.com/repos/tylerjclifton/mbta-reliability-analytics/actions/runs?per_page=1" \
  | python3 -c "import json,sys; r=json.load(sys.stdin)['workflow_runs'][0]; print(r['head_sha'][:7], r['status'], r['conclusion'])"
```
