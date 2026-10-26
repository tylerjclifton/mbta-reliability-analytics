# 0004 — Per-query byte limits instead of a project-wide daily query cap

**Status:** Accepted · **Date:** 2026-10-23

## Context
Google Cloud has no spending cap. The only hard stop is removing billing, which would stop ingest and permanently lose live alerts ([0001](0001-append-only-bronze.md)). A custom BigQuery `QueryUsagePerDay` quota was tried as a cap instead:
- At **50 GiB/day**, it refused transform queries once the day's usage reached about 11 GiB (Cloud Monitoring agreed on usage).
- Raised to **200 GiB/day**, it still refused queries at about 12 GiB.

Every hourly transform failed from 20:35 UTC until it was removed.

## Decision
- The project quota is pinned back at Google's default in Terraform (`infra/quotas.tf`). A quota preference can't be deleted, so it stays in code to keep Terraform and GCP matching.
- Cost is bounded **per query** with `maximum_bytes_billed`: 50 GiB for dbt (`transform/profiles.yml`) and 1 GiB for the dashboard (`serve/app.py`). The dbt limit started at 10 GiB and was raised on 2026-10-24: after the alerts cutover ([0002](0002-raw-alert-capture.md)), a full rebuild of the alerts table reads every alert snapshot (~2.6 GB/year) and would have hit 10 GiB in about 4 years.
- A $5/month billing budget emails at 50/90/100% and on forecast. It alerts only, and was created outside Terraform because the CI deployer has no billing access.

## Consequences
- A single runaway query fails before it runs. A loop of many small queries isn't capped, but the budget email catches it.
- Don't lower the daily quota again as a cost cap. It misfires regardless of its value.
