# 0013 — Bronze tables are defined in Terraform, not by ingest or dbt

**Status:** Accepted · **Date:** 2026-10-31

## Context
Bronze tables need a single owner for their schema, partitioning, and protection. Other options were considered:
- **Ingest jobs create their own tables** (schema autodetect or a schema in Python). Schemas would be scattered across jobs, a new or misspelled column would quietly widen the table, and nothing would stop a job from dropping one.
- **dbt owns them.** dbt only reads bronze ([0001](0001-append-only-bronze.md)), and the ingest jobs, which write it, have no dbt in their images.

Until now this choice was recorded only in a comment in `infra/bigquery.tf`, with pieces scattered across [0001](0001-append-only-bronze.md), [0002](0002-raw-alert-capture.md), [0006](0006-deploy-only-through-ci.md), and [0012](0012-local-ingest-writes-dev-bronze.md).

## Decision
- Every bronze table is defined once in `local.bronze_tables` (`infra/bigquery.tf`): columns, descriptions, clustering, and partitioning by ingest day. The audit columns are added to every table from one list.
- Ingest jobs load against the live table's schema (`ingest/common/load.py`), so a missing or misnamed column fails the load instead of creating a mismatched table.
- Every bronze table has `deletion_protection`, and the bronze dataset has `prevent_destroy`. No apply can drop history, even by mistake.
- `dev_bronze` is built from the same definitions ([0012](0012-local-ingest-writes-dev-bronze.md)), so the two can't drift.

**Which schema changes are safe.** Terraform updates a table in place, or replaces it (delete and recreate). Replacing a bronze table would lose its history, and the protections above block it:
- **In place, through Terraform as usual:** adding a column (always nullable; older rows read NULL), changing a description, changing clustering.
- **Replacement, so never through Terraform:** renaming a table, removing a column, changing a column's type, changing partitioning. A new column alongside the old is almost always the better fix. A rename is the one out-of-band change with a set procedure (below).

**Renaming a bronze table** is the one standing exception to [0005](0005-terraform-only-changes.md):
1. Rename it in BigQuery (`ALTER TABLE … RENAME TO …`). For a live table, do it right after an ingest run and point its job at the new name within seconds, before the next run fires.
2. Change the name in `infra/bigquery.tf` and add an `import` block that adopts the renamed table under the new name, so the plan shows no replacement. Remove the block once applied.
3. For a live table, run the job by hand and confirm rows land in the new table before pushing.

## Consequences
- Bronze schemas live in one reviewed file, and every schema change shows up in `terraform plan`.
- A new source's tables have to exist before its models read them, which is why tables and ingest are pushed before models ([0006](0006-deploy-only-through-ci.md)).
- Renames take the manual steps above. Both alert-table renames used them with no data lost ([0002](0002-raw-alert-capture.md)).
