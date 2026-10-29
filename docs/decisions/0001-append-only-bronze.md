# 0001 — Bronze is append-only; never rely on a source keeping history

**Status:** Accepted · **Date:** 2026-07 (formalized 2026-10)

## Context
Several sources keep little or no history. The MBTA alerts API drops an alert the moment it ends, and the NWS API kept only about 7 days. In July 2026, bronze was rebuilt during a schema change, and May–June 2026 weather was lost for good because the source no longer had it.

## Decision
- Every ingest run **appends** what it saw to bronze. Rows are never updated or deleted.
- Silver picks the latest version of each record (`keep_latest_version` macro, or an incremental table where re-reading all history would cost too much).
- Bronze tables are deletion-protected in Terraform, and the dataset has `prevent_destroy`.
- A schema change must never require dropping or rebuilding a bronze table. Renames are done in place (BigQuery `ALTER TABLE … RENAME`) or by copy, never by Terraform replacement.
- Paying a little beyond the free tier to keep history is acceptable.

## Consequences
- Bronze grows with every run (alerts: ~15 GB/year of full JSON in `bronze.mbta_alerts`, every mode since [0011](0011-capture-every-mode.md); the frozen `mbta_alerts_legacy` no longer grows). That's fine, and storage stays near-free for years.
- Since rows can't be removed, a local run can't write to production bronze by accident: it goes to `dev_bronze` ([0012](0012-local-ingest-writes-dev-bronze.md), 2026-10-29).
- Bronze should hold what the source said, not a selection of it. Where an ingest only kept chosen columns, the rest was lost (see [0002](0002-raw-alert-capture.md)).
