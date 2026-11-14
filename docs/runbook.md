# Runbook

How to do the occasional operational tasks. Every command assumes `gcloud` is signed in to `mbta-reliability-analytics` ([setup](setup.md)), and jobs run in `us-east1`.

## Jobs

### Run a job now

```bash
gcloud run jobs execute <job> --region us-east1 --wait   # ingest-mbta-alerts, ingest-mbta-stops, transform, …
```

A transform run started this way builds everything, including the slow-changing models the hourly runs skip ([0017](decisions/0017-slow-changing-models-build-daily.md)). Run one after a weather, ridership, stops, or shapes backfill to show it on the dashboard before the next daily run.

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
gcloud run jobs execute ingest-mbta-gated-entries --region us-east1 --update-env-vars FROM_ARCHIVE=true --wait
```

### Backfill ferry trips

`ingest-mbta-ferry-trips` re-pulls the last year of service each week, since the MBTA publishes ferry trips months late ([0018](decisions/0018-ridership-for-every-mode.md)). The whole layer (2018-11 on, ~400,000 trip legs) was loaded once when the job was added; re-run it whole only if the MBTA revises older years.

```bash
gcloud run jobs execute ingest-mbta-ferry-trips --region us-east1 --wait --update-env-vars LOOKBACK_DAYS=4000
```

### Load the LAMP alerts archive

`ingest-lamp-alerts` runs weekly and loads only the rows LAMP modified in the last two weeks: the alerts the 15-minute snapshots missed, and the MBTA's close times ([0016](decisions/0016-alerts-before-capture-from-lamp.md)). Run it by hand after a missed week, or with a longer window to pick up a correction LAMP makes to older alerts; silver drops the rows a load repeats.

Keep whole-file loads rare. One adds the whole archive to bronze (~3.4 GB uncompressed, several minutes in ~50 batches), and `silver.lamp_alerts__base` rereads every load after a new one, so a dozen would push that rebuild past the 50 GiB per-query limit.

```bash
gcloud run jobs execute ingest-lamp-alerts --region us-east1 --wait                                       # the usual two weeks
gcloud run jobs execute ingest-lamp-alerts --region us-east1 --wait --update-env-vars LOOKBACK_DAYS=4000  # the whole file
```

### Rebuild an incremental silver table

The three incremental silver tables skip what they've already processed: `silver.mbta_alerts__base` reads only new snapshots, `silver.lamp_alerts__base` reads bronze only when there's a new LAMP load, and `silver.mbta_ferry_trips__base` reads only new ferry loads. If their logic changes in a way that needs history reprocessed, rebuild them from bronze. A rebuild costs cents, but rebuilding the snapshot table reads every alert snapshot, so it outgrows the 50 GiB per-query limit around mid-2030 ([roadmap](roadmap.md#dated-upkeep)).

```bash
cd transform
dbt build --no-partial-parse --profiles-dir . --target local --full-refresh --select <model>   # in dev_silver first
dbt build --no-partial-parse --profiles-dir . --target gcp   --full-refresh --select <model>   # then production silver
```

The second command runs with your own credentials against production silver. It rebuilds only that table from bronze, and bronze is never touched. The next hourly transform carries on incrementally from there.

**Adding a column to one of these tables needs this rebuild right after the deploy.** Each incremental run reads the table's existing rows back to merge them, so a new column fails the run until the table has it (2026-11-05: the deploy's transform failed on `alert_closed_at`, and every hourly run would have too). Push, then rebuild production straight away and rerun the transform: `gcloud run jobs execute transform --region us-east1 --wait`. Gold keeps the last good build meanwhile.

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

1. Push the ingest job, its bronze table (`local.bronze_tables` in `infra/bigquery.tf`), and its schedule, with no models that read it. Declare the table in `transform/models/bronze/_bronze__sources.yml` with no freshness check yet, so prose may name it (the conventions check) and the deploy's freshness check skips it.
2. Once that deploy passes, seed the table: `gcloud run jobs execute ingest-<source>-<entity> --region us-east1 --wait`. Check the rows landed in `bronze.<source>_<entity>`.
3. Push the table's freshness check and the models that read it.

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

   Each job's `BQ_TABLE_ID` is looked up from its name (`ingest-<source>-<entity>` writes `<source>_<entity>`, in `infra/cloud-run-jobs.tf`). If a live table's new name doesn't match its job, the plan fails to find the table. Either set the job's `table` to the new name, or rename the job too.

   **Renaming a job takes two pushes.** Every Cloud Run job has deletion protection on, and Terraform can't destroy a job whose state still says so (2026-11-14: the ridership rename's first apply stopped there). So the first push adds the new job and keeps the old one, unscheduled, with `deletion_protection = false` and `table` set to the renamed table. Once it's applied, the second push removes the old job, along with the `import` blocks.
4. Plan locally: it must show 1 import and 0 to destroy. Push, and remove the `import` block in a follow-up commit once it's applied.
