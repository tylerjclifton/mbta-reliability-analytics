# Runbook

How to do the occasional operational tasks. Every command assumes `gcloud` is signed in to `mbta-reliability-analytics` ([setup](setup.md)), and jobs run in `us-east1`.

## Jobs

### Run a job now

```bash
gcloud run jobs execute <job> --region us-east1 --wait   # ingest-mbta-alerts, ingest-mbta-stops, transform, …
```

An ingest job run this way appends to production bronze, which is permanent ([0001](decisions/0001-append-only-bronze.md)). To try out an ingest change, run the script locally instead: it writes to `dev_bronze` ([0012](decisions/0012-local-ingest-writes-dev-bronze.md)).

```bash
PYTHONPATH=ingest python ingest/<job>/main.py   # → dev_bronze.<table>; rows expire after 7 days
```

### Backfill weather

NOAA revises recent days, so the job re-pulls a window. Widen it for a one-off backfill (800 days is about 2 years). The override applies to that execution only. Weather should reach back as far as ridership (2014-01-01 since 2026-11-03), or the transform warns about ridership days without weather.

```bash
gcloud run jobs execute ingest-noaa-weather --region us-east1 --update-env-vars LOOKBACK_DAYS=800
```

### Backfill ridership

The ridership layer holds only its last two years. Days before 2024-10-01 come from the MBTA's yearly archive, loaded by the same job in archive mode ([0015](decisions/0015-ridership-history-from-archive.md)). It was loaded once, on 2026-11-03; re-run it only if the MBTA revises past years.

```bash
gcloud run jobs execute ingest-mbta-ridership --region us-east1 --update-env-vars FROM_ARCHIVE=true --wait
```

### Load the LAMP alerts archive

`ingest-lamp-alerts` has no schedule: it supplies alerts from before the project's own full-JSON capture ([0016](decisions/0016-alerts-before-capture-from-lamp.md)), so one load covers it. It takes several minutes (5M+ rows in ~50 batches). Re-run it only to pick up a correction LAMP makes to old alerts; silver drops the rows a new load repeats.

Don't put it on a schedule. Each load adds the whole archive to bronze (~3.4 GB uncompressed), and `silver.lamp_alerts__base` rebuilds from every load after a new one, so a dozen loads would push that rebuild past the 50 GiB per-query limit. Regular reloads need the model to read only the newest complete load first ([roadmap](roadmap.md)).

```bash
gcloud run jobs execute ingest-lamp-alerts --region us-east1 --wait
```

### Rebuild an incremental silver table

`silver.mbta_alerts__by_route` and `silver.mbta_alerts__base` only read new snapshots each run. If their logic changes in a way that needs history reprocessed, rebuild them from bronze. A rebuild costs cents, but it reads every alert snapshot, so it outgrows the 50 GiB per-query limit around mid-2030 ([roadmap](roadmap.md)).

```bash
cd transform
dbt build --no-partial-parse --profiles-dir . --target local --full-refresh --select <model>   # in dev_silver first
dbt build --no-partial-parse --profiles-dir . --target gcp   --full-refresh --select <model>   # then production silver
```

The second command runs with your own credentials against production silver. It rebuilds only that table from bronze, and bronze is never touched. The next hourly transform carries on incrementally from there.

`--no-partial-parse` makes dbt re-read every model's settings instead of trusting its cache in `target/`. On 2026-11-03 a stale cache had lost the folders' `+schema`, and a local build wrote to production silver. The local profile now falls back to `dev_silver` (`transform/profiles.yml`), but production commands have no such net. Before a production rebuild, check where the model will land: `dbt ls --no-partial-parse --profiles-dir . --target gcp --select <model> --output json --output-keys "name schema"`.

## Deploys

### Check what's deployed

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

### Roll back a deploy

Re-run the GitHub Actions deploy for an earlier commit, or revert the commit and push. Artifact Registry keeps the 5 most recent images ([0006](decisions/0006-deploy-only-through-ci.md)).

### Add a new source

Every deploy ends with a transform run, whose freshness check fails on an empty bronze table. So a new source ships in two pushes ([0006](decisions/0006-deploy-only-through-ci.md)):

1. Push the ingest job, its bronze table (`local.bronze_tables` in `infra/bigquery.tf`), and its schedule, with no models that read it.
2. Once that deploy passes, seed the table: `gcloud run jobs execute ingest-<source>-<entity> --region us-east1 --wait`. Check the rows landed in `bronze.<source>_<entity>`.
3. Push the source declaration (`transform/models/bronze/_bronze__sources.yml`) and the models that read it.

### Clean up after renaming a dbt model

dbt doesn't drop a renamed model's old view or table, so it stays in `silver` or `gold` until removed ([0010](decisions/0010-silver-naming-and-materialization.md)). After the deploy that renames it passes, confirm the new object exists, then drop the old one:

```bash
bq ls mbta-reliability-analytics:silver                        # the new name is there
bq rm -f -t mbta-reliability-analytics:silver.<old_model_name>
```

These are dbt's objects, not Terraform's, so this isn't drift. Never run `bq rm` on anything in `bronze`.

## Maintenance

### Check that alert emails work

Safe, and touches no data. It fails the yearly routes job on purpose: attempt 1 only warns, attempt 2 alerts, so it also exercises the retry logic. Last verified end to end on 2026-10-31 (email from `alerting-noreply@google.com`).

```bash
gcloud run jobs execute ingest-mbta-routes --region us-east1 --wait \
  --args=-c,"import sys; sys.argv = ['mbta-routes/main.py']; from common import run; raise RuntimeError('TEST ALERT - deliberate failure; no data was touched')"
```

Don't put commas in the Python code, since `--args` splits on them. The email arrives within about a minute. The test leaves a failed execution in the job's history, which is expected.

### Rotate the MBTA API key

```bash
printf '%s' "<new key>" | gcloud secrets versions add mbta-api-key --data-file=-
```

Jobs read the `latest` version at their next run.

### Rename a bronze table

Terraform can rename a table only by replacing it, which would lose its history, so a rename is done in BigQuery and then adopted ([0013](decisions/0013-bronze-tables-in-terraform.md)). For a live table, start right after an ingest run so the next one is about 15 minutes off.

1. Rename it, and for a live table point its job at the new name straight away:

   ```bash
   bq query --use_legacy_sql=false \
     'ALTER TABLE `mbta-reliability-analytics.bronze.<old_name>` RENAME TO <new_name>'
   gcloud run jobs update ingest-<job> --region us-east1 --update-env-vars BQ_TABLE_ID=<new_name>
   ```

   To check the SQL first without renaming anything, run the same `bq query` with `--dry_run`.

2. For a live table, run the job (`gcloud run jobs execute ingest-<job> --region us-east1 --wait`) and confirm rows landed in `bronze.<new_name>`.
3. In `infra/bigquery.tf`, change the key in `local.bronze_tables` and add a block that adopts the renamed table:

   ```hcl
   import {
     to = google_bigquery_table.bronze["<new_name>"]
     id = "projects/${var.project_id}/datasets/bronze/tables/<new_name>"
   }
   ```

   Each job's `BQ_TABLE_ID` is looked up from its name (`ingest-<source>-<entity>` writes `<source>_<entity>`, in `infra/cloud-run-jobs.tf`). If a live table's new name doesn't match its job, the plan fails to find the table. The job then needs renaming too, or an override of its own.
4. Plan locally: it must show 1 import and 0 to destroy. Push, and remove the `import` block in a follow-up commit once it's applied.
