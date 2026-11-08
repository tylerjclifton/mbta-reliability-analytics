# 0017 — Slow-changing models are built and tested once a day, not hourly

**Status:** Accepted · **Date:** 2026-11-07

## Context
The transform runs every hour so new alerts reach the dashboard quickly, and every run built every model and ran every test. Once data tests were added (week of 2026-10-19), its query volume went from about 49 GiB to 250 GiB a week, slightly more than BigQuery's free 1 TiB a month. Each test query is billed at or near the 10 MB per-query minimum, so cost follows how many tests run, not how much data there is.

Shapes, ridership, and weather change at most once a day (their ingests run daily or weekly), as do the gold station, shape, and ridership tables built from them and from stops. Yet their models and tests ran 24 times a day, rechecking the same data. In the week before this change they billed 51 GiB, about 17% of the transform.

Options rejected:
- **Running every test less often.** Alerts change every 15 minutes, and a failing test is what keeps bad alert data out of gold.
- **Building a model only when its bronze table has new rows.** dbt can select on that (`source_status:fresher`), but only by comparing against the previous run's artifacts, which a stateless Cloud Run job doesn't keep. A daily run gets nearly the same saving with no state.
- **Moving routes and stops to the daily run too.** The hourly alert models join them, so a bad snapshot could reach gold before its tests ran.

## Decision
- Models tagged `daily` in `transform/dbt_project.yml` are built and tested only by a full run once a day, after the morning ingests (`transform_full_schedule` in `infra/variables.tf`). The tagged models are silver shapes, ridership, and weather, and gold `rail_stations`, `rail_shapes`, and `rail_ridership`. Excluding a model also excludes its tests.
- A model gets the tag only if no hourly model reads it.
- The hourly trigger passes `DBT_EXCLUDE=tag:daily`, which `transform/run.py` hands to `dbt build --exclude`. Every other run builds everything: the daily trigger, CI's post-deploy run, and manual runs.
- Freshness checks still run every hour, for every source.

## Consequences
- A new weather, ridership, shapes, or stops snapshot reaches gold at the next daily run, about an hour after the morning ingests, rather than at the next hourly run. After a backfill, a manual transform run shows it sooner ([runbook](../runbook.md)).
- `rail_ridership`'s incident columns refresh daily. Its rows are days the ridership layer has already published, at least several days old, so their incidents rarely change.
- A failing daily test is caught once a day. Its gold table keeps its last good build until a full run passes.
- The hourly trigger passes an override, so the scheduler's service account holds `run.jobsExecutorWithOverrides` on the transform job (`infra/iam.tf`); `run.invoker` can't pass overrides.
- A new model has to decide whether it's `daily`. The test is whether any hourly model reads it.
