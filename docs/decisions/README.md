# Decision records

One short file per decision that shaped this project: the situation, what was decided, and what follows from it. They answer "why is it like this?" when the code alone can't.

Numbers are assigned in the order records are written and never change. The index groups them by topic.

## Data capture

| # | Decision | Status |
|---|---|---|
| [0001](0001-append-only-bronze.md) | Bronze is append-only; never rely on a source keeping history | Accepted |
| [0002](0002-raw-alert-capture.md) | Capture each alert's full JSON; freeze the shaped table as legacy | Accepted |
| [0011](0011-capture-every-mode.md) | Capture the whole alerts feed (every mode); silver keeps rail | Accepted |
| [0012](0012-local-ingest-writes-dev-bronze.md) | Local ingest runs write to `dev_bronze`, never production bronze | Accepted |
| [0013](0013-bronze-tables-in-terraform.md) | Bronze tables are defined in Terraform, not by ingest or dbt | Accepted |
| [0015](0015-ridership-history-from-archive.md) | Ridership before the live layer comes from the MBTA's yearly archive, into the same bronze table | Accepted |
| [0016](0016-alerts-before-capture-from-lamp.md) | Alerts from before full-JSON capture come from the MBTA's LAMP archive | Accepted |
| [0018](0018-ridership-for-every-mode.md) | Ridership for every mode from the MBTA's monthly figures; ferry trips with their times | Accepted |

## Modeling

| # | Decision | Status |
|---|---|---|
| [0003](0003-stations-as-bridge-table.md) | Alert stations live in a bridge table, not a new alert grain | Accepted |
| [0008](0008-build-for-the-end-state.md) | Build metrics for the end state, with data thresholds | Accepted |
| [0010](0010-silver-naming-and-materialization.md) | Silver models are `<bronze table>__<step>`; views unless too costly to recompute | Accepted |

## Infrastructure and operations

| # | Decision | Status |
|---|---|---|
| [0004](0004-per-query-cost-limits.md) | Per-query byte limits instead of a project-wide daily query cap | Accepted |
| [0005](0005-terraform-only-changes.md) | Every infrastructure change goes through Terraform | Accepted |
| [0006](0006-deploy-only-through-ci.md) | Deploy only by pushing to `main` | Accepted |
| [0007](0007-dashboard-scales-to-zero.md) | The dashboard scales to zero; cold starts are acceptable | Accepted |
| [0009](0009-runtime-versions.md) | dbt 1.12 and Python 3.13; dbt v2 skipped for now | Accepted |
| [0014](0014-bronze-physical-storage-billing.md) | Bill bronze storage on physical (compressed) bytes | Accepted |
| [0017](0017-slow-changing-models-build-daily.md) | Slow-changing models are built and tested once a day, not hourly | Accepted |

## Writing one

Every record has the same shape:
- **Title:** `# 00NN — <the decision, stated as a rule>`. The index row uses the same words.
- **Status line:** `**Status:** <Accepted | Superseded by 00NN> · **Date:** <YYYY-MM-DD it was decided, or written down for a long-standing practice>`. Status is one word or the superseding record, nothing else.
- **Context:** the situation that forced a choice, and any options rejected.
- **Decision:** what was decided, in bullets or numbered steps.
- **Consequences:** what follows from it, good and bad.
- **History** (only if needed): dated refinements made after the record was accepted, oldest first.

A figure that changes over time (a growth rate, a date a limit is reached) is stated in one record and linked from the others, so it's only ever updated in one place.

**Adding one:** take the next number, follow the shape above, and add a row to the matching table here.

**Changing one:** refinements made while a decision is still being carried out (a better name, a step done sooner than planned) are added to the record's History section, dated, so it tells the whole story. Reversing a decision later gets a new record, and the old one is marked "Superseded by 00NN".
