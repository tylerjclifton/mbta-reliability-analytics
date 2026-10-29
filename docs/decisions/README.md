# Decision records

One short file per decision that shaped this project: the situation, what was decided, and what follows from it. They answer "why is it like this?" when the code alone can't.

| # | Decision | Status |
|---|---|---|
| [0001](0001-append-only-bronze.md) | Bronze is append-only; never rely on a source keeping history | Accepted |
| [0002](0002-raw-alert-capture.md) | Capture each alert's full JSON; freeze the shaped table as legacy | Accepted (cut over 2026-10-24) |
| [0003](0003-stations-as-bridge-table.md) | Alert stations live in a bridge table, not a new alert grain | Accepted |
| [0004](0004-per-query-cost-limits.md) | Per-query byte limits instead of a project-wide daily query cap | Accepted |
| [0005](0005-terraform-only-changes.md) | Every infrastructure change goes through Terraform | Accepted |
| [0006](0006-deploy-only-through-ci.md) | Deploy only by pushing to `main` | Accepted |
| [0007](0007-dashboard-scales-to-zero.md) | The dashboard scales to zero; cold starts are acceptable | Accepted |
| [0008](0008-build-for-the-end-state.md) | Build metrics for the end state, with data thresholds | Accepted |
| [0009](0009-runtime-versions.md) | dbt 1.12 and Python 3.13; dbt v2 skipped for now | Accepted |
| [0010](0010-silver-naming-and-materialization.md) | Silver models are `<bronze table>__<step>` (`__base` = cleaned copy); views unless too costly to recompute | Accepted |
| [0011](0011-capture-every-mode.md) | Capture the whole alerts feed (every mode); silver keeps rail | Accepted |
| [0012](0012-local-ingest-writes-dev-bronze.md) | Local ingest runs write to `dev_bronze`, never production bronze | Accepted |

**Adding one:** copy the shape of an existing file, take the next number, add a row here.

**Changing one:** refinements made while a decision is still being carried out (a better name, a step done sooner than planned) are added to the record itself, dated, so it tells the whole story. Reversing a decision later gets a new record, and the old one is marked "Superseded by 00NN".
