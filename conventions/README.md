# Conventions — how code, comments, docs, and commits are written

These rules are general: they apply to any project, so every part of every project reads the same. This folder is meant to be copied into each project as is: this page, and [`check.py`](check.py), which enforces what a script can judge. A project adds its own specifics in `docs/conventions.md`. To change a rule, change it here and in `check.py` together, then copy the folder to the other projects.

## Tools

Formatting a tool can check is left to the tool: a formatter or linter for each language, plus [`check.py`](check.py) for the rules on this page a script can judge (widths, banners, punctuation, ellipses, spelling, and references that no longer resolve). CI runs them all on every push. Each project lists its tools in its own `docs/conventions.md`. What no tool can judge is left to review.

## Writing

These rules cover all prose: comments, docstrings, docs, and commit messages.

- **Say what it does and why**, wherever that isn't obvious at a glance. Don't repeat what the code already says.
- **Each fact lives in one place.** Thresholds, formulas, and figures sit next to the code that sets them; elsewhere, describe them rather than copying the number. A short repeated explanation is fine where it saves opening another file, and a pointer always comes with a one-line summary.
- **Docs change with the code**, in the same commit: README, model headers and YAML, `docs/`. A new decision gets a record in `docs/decisions/`.
- **Date what will go stale.** A measured figure or a checked fact carries the date it was true: "peak memory, measured 2026-11-03: 1.1 GB".
- **American spelling** (color, canceled), to match code identifiers.
- **Refer to decisions by number:** "decision 0016" in code, a link in docs.
- **Typography:**
  - **Em dash:** spaced ( — ), to join a name to what it is or to set off an aside.
  - **En dash:** for ranges (2014–2019).
  - **×:** for a grain ("one row per incident × route").
  - **→:** for "becomes" or "leads to".
  - **…:** for something left out, never three periods.
  - **Dates:** `YYYY-MM-DD` in code and records.

## Punctuation

Prose is punctuated by what it's for, not by counting its sentences:

- **Explanations end with a period**, even a one-line fragment. That's every full-line comment, and every paragraph of a docstring, file header, or YAML description. A paragraph may end with a colon instead when it introduces a list or code, with a question mark, or with a URL.
- **Titles and labels don't:**
  - a file's title (its first line), the title inside a `═` box, and a section banner
  - an import-group label: `# Import standard libraries`
  - a group heading in a list file (`requirements.txt`, `.gitignore`): `# Linting`
  - an end-of-line comment: `timeout = "600s"  # 10 minutes`
  - a table cell, or a line of a code sample
- **A list has one ending.** If any item runs to two sentences, every item ends with a period; otherwise none does.
- **Ending on code or a link:** a command at the end of a sentence goes in backticks before the period. A URL goes on its own line, with no period after it.

```python
# Import standard libraries
import logging

# One request per route. A route with no shapes fails the job before anything
# loads.
for route_id in ROUTES:
    timeout = 30  # seconds
```

## Comments

- **Width:** prose in comments, docstrings, file headers, and YAML descriptions wraps at 80 columns, the width of the section banners. A table or code sample can't be rewrapped without losing its shape, so it may run to 120, like code. The check counts a line as one when it's indented past its block's prose or has aligned columns (a gap of two or more spaces).
- **Section banners,** 80 columns wide:
  ```text
  # ══════════════════════════════════════════════════════════════════════════════
  # Title — what this file or part is
  # ══════════════════════════════════════════════════════════════════════════════

  # ── Subsection ────────────────────────────────────────────────────────────────
  ```
  The box opens Terraform and YAML files and marks the main parts of a long file. The single line marks a subsection anywhere. SQL uses `--` in place of `#`.

## File headers

Every file opens with a one-line title, `<name> — <what it is>`, with no period, then a blank line. Paragraphs below it say whatever a reader needs before the code. The form depends on the file type.

**Python.** The module docstring's first line is the title. Function and class docstrings open with a summary sentence that ends with a period. Imports sit in labeled groups, standard library first, the last label saying what's imported:
```python
# Import standard libraries
import logging

# Import third party libraries
import pandas as pd

# Import the project's own helpers
from common.fetch import fetch
```
A test module's title names what it tests (`Ingest job tests — each script, run against canned responses`); test names state the behavior as a phrase.

**dbt models.** A `{# … #}` header: the title (`<schema>.<model> — one row per <grain>`), what the model holds and why it's built that way, then its numbered steps. Each step is a CTE named after it, under a matching numbered comment:
```sql
{#
  silver.orders__base — one row per order

  What the model holds, and why it's built this way.

  Steps:
    1. latest_versions — latest snapshot per order
    2. final select    — renamed to project conventions
#}

WITH

    -- 1. Latest snapshot per order.
    latest_versions AS (
        …
    )
```
Columns run keys first, then attributes, then audit columns, with `AS` aligned. Jinja strings take single quotes, except inside a SQL string literal, where double quotes keep the quoting readable: `'{{ var("local_timezone") }}'`.

**dbt macros and tests** carry a `{#- … -#}` docblock inside the definition, like a function docstring: a summary sentence, a usage example, and, for a macro, what it compiles to. A singular test opens with a comment saying what a failing row means and why the test has its severity.

**dbt YAML.** `version: 2`, then the boxed header. Long descriptions are folded with `>`. A column that appears in several models takes its description from one doc block through `{{ doc('name') }}`. Each test sits with the model or column it guards.

**Terraform.** A boxed header, then related variables and resources grouped under `# ── Group ──` banners. Every variable has a description.

**Everything else** (Dockerfiles, shell scripts, TOML, requirements, ignore files) opens with plain `#` lines. Dependencies are pinned with `==`, each component's in its own `requirements.txt`.

## Naming

| Thing | Convention | Example |
|---|---|---|
| Datasets | Medallion layer | `bronze`, `silver`, `gold` |
| Bronze tables | `<source>_<entity>`; `_legacy` marks a frozen table kept as history | `noaa_weather`, `shop_orders_legacy` |
| Silver models | `<bronze table>__<step>`; `__base` is the cleaned copy | `shop_orders__base`, `shop_orders__by_customer` |
| Gold tables | `<domain>_<entity>` | `sales_daily_revenue` |
| Bronze columns | The source system's names, plus audit columns | `tmax` |
| Silver and gold columns | `snake_case`; keys `<entity>_id`; `_at` = TIMESTAMP (UTC); `_date` = DATE (the project's local time zone); measures carry their unit; booleans `is_` | `order_placed_at`, `precipitation_in`, `is_refunded` |
| Audit columns | On every bronze table, carried into silver and gold where a row has one source version | `ingested_at`, `ingested_by` |
| dbt CTEs | Named after the step they perform | `latest_versions` |
| Python | `snake_case` functions and variables; `UPPER_CASE` module constants | `append_to_bronze`, `BATCH_ROWS` |
| Tests | `test_<subject>_<what it does>`, as a phrase | `test_fetch_reports_a_network_error` |
| Terraform | `snake_case` resource names; `kebab-case` names in GCP | `google_service_account.job_scheduler` → `job-scheduler` |
| Environment variables | `UPPER_SNAKE_CASE`, prefixed by the system the setting configures: `GCP_` the cloud project, `BQ_` BigQuery datasets and tables, `DBT_` dbt, a source's name for its API; a job's own settings take none. A setting several components share has one name in all of them | `GCP_PROJECT_ID`, `BQ_DATASET_ID`, `DBT_TARGET`, `WEATHER_API_KEY`, `LOOKBACK_DAYS` |

## Docs

Every doc has one job, and a fact lives in only one of them:

| Doc | Holds |
|---|---|
| `README.md` | The project for a first-time reader: what it does, architecture, cost, stack, development and deployment |
| `docs/setup.md` | Getting a new machine ready, in numbered steps |
| `docs/runbook.md` | Occasional operational tasks, step by step |
| `docs/decisions/` | Why things are as they are, one record per decision; the record format is in its README |
| `docs/roadmap.md` | Planned work. An item moves to a decision record once decided, and is deleted once done |
| `conventions/` | These general conventions and their check, copied between projects |
| `docs/conventions.md` | The project's own conventions, on top of these |
| `CLAUDE.md` | Guardrails and pointers for AI coding sessions. It summarizes the docs and is never the only place a rule lives |

Markdown style:
- **Openings:** each doc opens with its title and one short paragraph: what it's for and when to read it.
- **Headings:** sentence case. Runbook headings are tasks, phrased as commands ("Rotate the API key").
- **Paragraphs:** one line per paragraph, never wrapped by hand.
- **Bold lead-ins:** a list item that makes one point leads with it in bold: "**Bronze is append-only.** Never …".
- **Backticks:** for identifiers, tables, commands, and paths: `bronze.shop_orders`, `dbt build`.
- **Links:** relative, and to the section where one exists, e.g. `[runbook](runbook.md#add-a-new-source)`.

## Commits

- **Subject:** imperative, sentence case, no closing period, short enough to read in a one-line log (about 72 characters). It says what changed, as a reader of the log would want it: "Name each affected stretch on the map by its ends".
- **Body:** what changed and why, wrapped by hand under 80 columns. A long body can group paragraphs under a lead-in ("Error handling: …").
- **Same commit:** docs and tests go in with the change they describe.
- **No trailer:** no AI co-author trailer or "Generated with" line.

## Using these in a project

1. **Copy this folder** to the repo's root as `conventions/`.
2. **Run the check in CI** after the linters: `python conventions/check.py`. It reads the files git tracks, so every new file is held to the rules from its first commit.
3. **Write `docs/conventions.md`** for what's specific to the project: its tools and their configs, its data rules, and its patterns for each kind of file. Link it back here.
4. **Point the docs at both**, from the README and any guidance for AI coding sessions (`CLAUDE.md`).

**Keeping projects in step:** the copy in the project where a rule last changed is the source. Copy the folder from there to the others, and `diff -r` between two projects' copies shows what one is missing.

**A new file** needs only its one-line title, a blank line, and the header its file type calls for ([File headers](#file-headers)); the check flags anything it can judge before CI does.
