# 0001 — Bronze is append-only; never rely on a source keeping history

**Status:** Accepted · **Date:** 2026-10-24

## Context
Several sources keep little or no history. The MBTA alerts API drops an alert the moment it ends, and the NWS API kept only about 7 days. In July 2026, bronze was rebuilt during a schema change, and May–June 2026 weather was lost for good because the source no longer had it. The project has worked this way since then; this record writes the rule down.

## Decision
- Every ingest run **appends** what it saw to bronze. Rows are never updated or deleted.
- Silver picks the latest version of each record (`keep_latest_version` macro, or an incremental table where re-reading all history would cost too much).
- A schema change must never require dropping or rebuilding a bronze table. Bronze tables are protected from deletion in Terraform, and renames follow a set procedure instead of a Terraform replacement ([0013](0013-bronze-tables-in-terraform.md)).
- Bronze holds what the source said, not a selection of it.
- Paying a little beyond the free tier to keep history is acceptable.

## Consequences
- Bronze grows with every run, mostly alert snapshots ([0011](0011-capture-every-mode.md) has the current rate). Storage stays near-free for years.
- Since rows can't be removed, a local ingest run writes to `dev_bronze`, never production bronze ([0012](0012-local-ingest-writes-dev-bronze.md)).
- Where an ingest kept only chosen columns, the rest was lost for good ([0002](0002-raw-alert-capture.md)).
- One deliberate exception: other modes' route and stop history comes from the MBTA's own GTFS archive rather than bronze ([0011](0011-capture-every-mode.md)).
