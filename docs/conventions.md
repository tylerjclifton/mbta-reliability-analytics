# Conventions

How code, comments, docs, and commits are written here, so every part of the repo reads the same. Each rule comes from what the repo already does. To change one, change it here and in the code, in the same commit.

## Tools

Formatting that a tool can check is left to the tool. CI runs all three on every push; the commands to run them locally are in the README's [Development & deployment](../README.md#development--deployment).

| Files | Tool | Config | What it settles |
|---|---|---|---|
| Python | ruff | `pyproject.toml` | 120-character lines, single quotes, import order |
| dbt SQL | sqlfluff | `transform/.sqlfluff` | 120-character lines, uppercase keywords and functions, single-quoted literals |
| Terraform | `terraform fmt` | none | Indentation and alignment |

Everything below is what no tool checks.

## Naming

| Thing | Convention | Example |
|---|---|---|
| Datasets | Medallion layer | `bronze`, `silver`, `gold` |
| Bronze tables | `<source>_<entity>`; `_legacy` marks a frozen table kept as history | `mbta_alerts`, `mbta_alerts_legacy` |
| Silver models | `<bronze table>__<step>`; `__base` is the cleaned copy | `mbta_alerts__base`, `mbta_alerts__by_route` |
| Gold tables | `<domain>_<entity>` | `rail_ridership` |
| Ingest jobs | `ingest/<source>-<entity>/main.py` → `bronze.<source>_<entity>`; the Cloud Run job is `ingest-<source>-<entity>` | `ingest/noaa-weather` → `bronze.noaa_weather` |
| Bronze columns | Source system's names, plus audit columns | `route_or_line`, `tmax` |
| Silver / gold columns | `snake_case`; keys `<entity>_id`; `_at` = TIMESTAMP (UTC); `_date` = DATE (Eastern); measures carry their unit; booleans `is_` | `alert_start_at`, `precipitation_in`, `is_in_feed` |
| Audit columns | On every bronze table, carried into silver and gold where a row has one source version (alert models track `first_seen_at` / `last_seen_at` instead) | `ingested_at`, `ingested_by` |
| dbt CTEs | Named after the step they perform | `latest_versions`, `quality_checked` |
| Python | `snake_case` functions and variables; `UPPER_CASE` module constants | `append_to_bronze`, `BATCH_ROWS` |
| Tests | `test_<subject>_<what it does>`, as a phrase | `test_fetch_reports_a_network_error` |
| Terraform | `snake_case` resource names; `kebab-case` names in GCP | `google_service_account.job_scheduler` → `job-scheduler` |
| Environment variables | `UPPER_SNAKE_CASE`, one name per setting in every component; the GCP project is `GCP_PROJECT_ID` everywhere, and BigQuery targets start `BQ_` | `GCP_PROJECT_ID`, `BQ_DATASET_ID`, `LOOKBACK_DAYS` |

## Writing

These rules cover all prose: comments, docstrings, docs, and commit messages.

- **Say what it does and why**, wherever that isn't obvious at a glance. Don't repeat what the code already says.
- **Each fact lives in one place.** Thresholds, formulas, and figures sit next to the code that sets them; elsewhere, describe them rather than copying the number. A short repeated explanation is fine where it saves opening another file, and a pointer always comes with a one-line summary.
- **Docs change with the code**, in the same commit: README, dbt model headers and yml, `docs/`. A new decision gets a record in `docs/decisions/`.
- **Date what will go stale.** A measured figure or a checked fact carries the date it was true: "peak memory, measured 2026-11-03: 1.1 GB".
- **American spelling** (color, canceled), to match the code's identifiers.
- **Refer to decisions by number:** "decision 0016" in code, a link like [0016](decisions/0016-alerts-before-capture-from-lamp.md) in docs.
- **Typography:**
  - **Em dash:** spaced ( — ), to join a name to what it is or to set off an aside.
  - **En dash:** for ranges (2014–2019).
  - **×:** for a grain ("one row per incident × route").
  - **→:** for "becomes" or "leads to".
  - **…:** for something left out.
  - **Dates:** `YYYY-MM-DD` in code and records.

## Comments

- **Width:** comments, docstrings, dbt headers, and YAML descriptions wrap at 80 columns, the width of the section banners. Code may run to 120.
- **Periods:** a comment that is one sentence or a fragment has no closing period. A comment of two or more sentences ends every sentence with one, the last included. This covers every `#` and `--` comment, the block that opens a file included, and dbt's inline `{# … #}` comments; each paragraph and each list item counts on its own:
  ```python
  # ArcGIS sets exceededTransferLimit while more pages remain

  # ArcGIS sets exceededTransferLimit while more pages remain. An empty
  # page ends it too, so a stuck flag can't loop until the job times out.
  ```
- **Prose elsewhere:** docstrings, dbt model and macro headers, and YAML descriptions are prose, so their sentences end with periods. Their title lines, labeled fields (`Source:`), and list items don't. A docstring that only shows sample output (`"""45 min · 2.7 hr · 1 day · 12 days"""`) has no period.
- **Ending on code or a link:** a command at the end of a sentence goes in backticks before the period. A URL goes on its own line, with no period after it.
- **Section banners,** 80 columns wide:
  ```text
  # ══════════════════════════════════════════════════════════════════════════════
  # Title — what this file or part is
  # ══════════════════════════════════════════════════════════════════════════════

  # ── Subsection ────────────────────────────────────────────────────────────────
  ```
  The box opens Terraform and YAML files and marks the main parts of `serve/app.py`. The single line marks a subsection anywhere.

## File headers

Every file opens with a header: what it is, and anything a reader needs before the code. Its form depends on the file type.

### Python

A module docstring whose first line names what the file is. Imports sit in labeled groups, standard library first:
```python
# Import standard libraries
import logging

# Import third party libraries
import pandas as pd

# Import shared ingest helpers
from common.fetch import fetch
```
The last label says what is being imported (`# Import the helpers under test`).

**Ingest scripts** list their fields aligned, then any notes. The body runs in `# ── Fetch ──`, `# ── Shape ──`, and `# ── Load ──` sections:
```text
Source:     MBTA V3 API /shapes (https://api-v3.mbta.com)
Cadence:    Weekly (shapes rarely change)
Each run:   For each rail route, snapshots every shape the API returns
Writes to:  bronze.mbta_shapes (append) — one row per shape × route per run
```
A job that can backfill adds a `Backfill:` field.

Each step logs what it produced, in one form: `Fetched 412 alerts`, `Fetched Red: 22 stations, 140 child stops`, `Shaped 730 rows, 2024-11-01 to 2026-10-31`, `Appended 730 rows to <table>`. A failure goes through `fail()` and names the source and what was wrong: `The MBTA API returned no stops for any rail route`.

**Tests** open with "Tests for …" and the module under test.

### dbt models

A `{# … #}` header gives the model's name, its grain, what it holds and why it's built that way, then its numbered steps. Each step is a CTE named after it, under a matching numbered comment:
```sql
{#
  silver.mbta_stops__base — one row per stop × route

  What the model holds, and why it's built this way.

  Steps:
    1. latest_versions — latest snapshot per stop × route
    2. final select    — rename to project conventions, resolve station_id
#}

WITH

    -- 1. Latest snapshot per stop × route
    latest_versions AS (
        …
    )
```
Columns run keys first, then attributes, then audit columns, with `AS` aligned. Jinja strings take single quotes too, except inside a SQL string literal, where double quotes keep the quoting readable: `'{{ var("local_timezone") }}'`.

**Macros and generic tests** carry a `{#- … -#}` comment inside the definition: what it does, a usage example, and, for a macro, what it compiles to.

**Singular tests** open with a `--` comment saying what a failing row means, and why the test has its severity.

### dbt YAML

`version: 2`, then the boxed header. Long descriptions are folded with `>`. A column that appears in several models takes its description from `models/_docs.md` through `{{ doc('name') }}`. Each test sits with the model or column it guards.

### Terraform

A boxed header (`<Area> — <what it defines>`), then whatever a reader needs before the resources: naming, who reads them, and why they're shaped this way. Related variables and resources are grouped under `# ── Group ──` banners. Every variable has a description.

### Everything else

Dockerfiles, shell scripts, TOML, requirements, and ignore files open with plain `#` lines saying what the file is and what uses it. Dependencies are pinned with `==`, each component's in its own `requirements.txt`.

## Docs

Every doc has one job, and a fact lives in only one of them:

| Doc | Holds |
|---|---|
| `README.md` | The project for a first-time reader: what it does, the dashboard, architecture, cost, stack, development and deployment |
| `docs/setup.md` | Getting a new machine ready, in numbered steps |
| `docs/runbook.md` | Occasional operational tasks, step by step |
| `docs/decisions/` | Why things are as they are, one record per decision; the record format is in its [README](decisions/README.md) |
| `docs/roadmap.md` | Planned work. An item moves to a decision record once decided, and is deleted once done |
| `docs/conventions.md` | This page |
| `CLAUDE.md` | Guardrails and pointers for AI coding sessions. It summarizes the docs and is never the only place a rule lives |

The dashboard's display rules (time windows, statistics, wording, number formats, chart style) are in the header of `serve/app.py`, next to the code that follows them. Its colors and fonts are the design tokens near the top of the same file.

Markdown style:
- **Openings:** each doc opens with its title and one short paragraph: what it's for and when to read it.
- **Headings:** sentence case. Runbook headings are tasks, phrased as commands ("Rotate the MBTA API key").
- **Paragraphs:** one line per paragraph, never wrapped by hand.
- **Bold lead-ins:** a list item that makes one point leads with it in bold: "**Bronze is append-only.** Never …".
- **Backticks:** for identifiers, tables, commands, and paths: `bronze.mbta_alerts`, `dbt build`.
- **Links:** relative, and to the section where one exists, e.g. [runbook](runbook.md#add-a-new-source).

## Commits

- **Subject:** imperative, sentence case, no closing period, short enough to read in a one-line log (about 72 characters). It says what changed, as a reader of the log would want it: "Name each affected stretch on the map by its ends".
- **Body:** what changed and why, wrapped by hand under 80 columns. A long body can group paragraphs under a lead-in ("Error handling: …").
- **Same commit:** docs and tests go in with the change they describe.
- **No trailer:** no AI co-author trailer or "Generated with" line.
