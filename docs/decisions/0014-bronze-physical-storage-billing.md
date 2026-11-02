# 0014 — Bill bronze storage on physical (compressed) bytes

**Status:** Accepted · **Date:** 2026-11-01

## Context
BigQuery bills storage on one of two numbers per table, chosen per dataset:
- **Logical bytes** (the default): the data's uncompressed size, by BigQuery's fixed type sizes (8 bytes per INT64, a string's UTF-8 length + 2).
- **Physical bytes**: what the compressed, columnar storage actually takes, plus time-travel and fail-safe copies. The price per GB is about double.

Bronze compresses unusually well, because alert snapshots repeat the same JSON every 15 minutes for as long as an alert lasts. Measured 2026-11-01:

| Table | Logical | Physical |
|---|---|---|
| `bronze.mbta_alerts` | 192 MB | 1.6 MB (~118×) |
| `bronze.mbta_alerts_legacy` | 9.2 MB | 0.57 MB (~16×) |

On logical billing, alert storage grows with every year kept: about $18/year by year 10 and $36/year by year 20 at the [0011](0011-capture-every-mode.md) growth rate, before any new source. The project is meant to run for decades.

## Decision
- The `bronze` dataset uses `storage_billing_model = "PHYSICAL"` (`infra/bigquery.tf`), applied in place. The plan showed one in-place update and nothing replaced.
- **Silver, gold, and the dev datasets stay logical.** Gold tables are rebuilt every hour, and physical billing would also bill the 7 days of time travel each rebuild leaves behind. They're small, so logical is cheaper there.

## Consequences
- Bronze storage costs roughly 50× less: about double the price on ~100× fewer bytes. Decades of alert snapshots stay in the cents-to-dollars per year range.
- Query cost is unchanged: on-demand queries are billed on logical bytes scanned whatever the storage model, so the per-query limits ([0004](0004-per-query-cost-limits.md)) and the mid-2030 rebuild estimate ([0011](0011-capture-every-mode.md)) don't move.
- Time-travel and fail-safe bytes are now billed for bronze. Append-only tables create almost none (0 bytes on 2026-11-01), since only changed or deleted data lands there.
- The model can't be changed again for 14 days after a switch.
- A future bronze source that compresses poorly (few repeats) would cost up to twice as much as on logical. Check its two sizes after its first weeks: `bq show --format=prettyjson bronze.<table>` lists `numTotalLogicalBytes` and `numTotalPhysicalBytes`.
