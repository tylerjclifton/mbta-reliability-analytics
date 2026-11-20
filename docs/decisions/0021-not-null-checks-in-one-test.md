# 0021 — A model's not-null checks run as one test

**Status:** Accepted · **Date:** 2026-11-19

## Context
Every BigQuery query bills at least 10 MB, so the transform's cost follows how many tests it runs, not how much data they read ([0017](0017-slow-changing-models-build-daily.md)). dbt's `not_null` test is one query per column. By 2026-11-19 an hourly run's 75 tests billed 730 MiB, and 50 of them were `not_null`: 430 MiB a run spent confirming that columns were filled. Across the project, 108 of them checked 33 models.

Options rejected:
- **Model contracts with `not_null` constraints.** BigQuery would enforce them as each table is written, at no query cost. But a contract needs every column's name and type declared in YAML and kept in step with the SQL as models change: a lot of upkeep for one check.
- **A single `expression_is_true`-style test** (`a IS NOT NULL AND b IS NOT NULL`). One query too, but its failure says only that some row has a NULL, not which column.
- **Testing less often.** [0017](0017-slow-changing-models-build-daily.md) already rejected it: a failing test is what keeps bad alert data out of gold.

## Decision
- A model's not-null columns are listed in one model-level `not_null_columns` test (`transform/tests/generic/not_null_columns.sql`), which counts every column's NULLs in a single query and returns each column that has any.
- dbt's `not_null` stays only where one column needs its own severity: the two warnings in gold.

## Consequences
- An hourly run's tests bill 460 MiB instead of 730 (measured 2026-11-19), and the daily run's 181 tests became 106.
- Every check still runs in `dbt build`, before the models downstream of it, so a NULL still stops bad data reaching gold.
- A column's YAML no longer says it's required; the model's `not_null_columns` list does.
- A failure names the model, and its count is how many columns have NULLs. To see which, compile the test (`dbt compile --select <test name>`) and run its SQL in BigQuery.
