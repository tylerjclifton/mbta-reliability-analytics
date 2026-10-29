# 0012 — Local ingest runs write to dev_bronze

**Status:** Accepted · **Date:** 2026-10-29

## Context
dbt already had sandboxes: local builds (`--target local`) write to `dev_silver` and `dev_gold`, and read the real bronze. They don't need a dev bronze, since dbt only reads bronze, and testing against real data is the point.

Ingest jobs had no sandbox. `append_to_bronze()` defaulted to the production `bronze` dataset, and the README said a local run "writes to the real bronze table." Bronze rows are never deleted ([0001](0001-append-only-bronze.md)), so a bug tried out on a laptop would leave permanent rows in production. Nothing else in the system has that property: a broken model rebuilds from bronze, and a bad deploy rolls back.

## Decision
- A **`dev_bronze`** dataset holds a copy of every live bronze table, built in Terraform from the same schema definitions as bronze (`local.bronze_tables` in `infra/bigquery.tf`), so the two can't drift. Frozen `_legacy` tables are left out, since nothing writes them.
- **`append_to_bronze()` defaults to `dev_bronze`.** The Cloud Run jobs set `BQ_DATASET_ID=bronze` explicitly (`infra/cloud-run-jobs.tf`), so production is unchanged. Writing real bronze is something only the deployed jobs do: to run one now, use `gcloud run jobs execute` (runbook).
- Test rows expire after 7 days by **partition** (each table is partitioned by ingest day). dev_silver and dev_gold expire whole tables instead, which dbt recreates on the next build. Terraform owns the dev_bronze tables, so expiring them would make every deploy recreate them.

## Consequences
- A local ingest run is safe by default. It loads against the same schema as production, so schema mistakes still fail the load.
- dbt doesn't read dev_bronze. To see a local ingest run's rows, query `dev_bronze.<table>`; a local dbt build still reads the real bronze.
- Cost is effectively zero: test rows only, gone in a week.
