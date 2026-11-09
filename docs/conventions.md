# Conventions in this project

What's specific to this project, on top of the general conventions in [`conventions/`](../conventions/README.md): naming, punctuation, file headers, docs, and commits all follow those. To change a general rule, change it there; this page holds only what other projects don't share.

## Tools

CI runs all four on every push; the commands to run them locally are in the README's [Development & deployment](../README.md#development--deployment).

| Files | Tool | Config | What it settles |
|---|---|---|---|
| Python | ruff | `pyproject.toml` | 120-character lines, single quotes, import order |
| dbt SQL | sqlfluff | `transform/.sqlfluff` | 120-character lines, uppercase keywords and functions, single-quoted literals |
| Terraform | `terraform fmt` | none | Indentation and alignment |
| Everything | `conventions/check.py` | the script | The general conventions' widths, banners, punctuation, ellipses, spelling, and references |

## Data

- **Time zone:** `_date` columns are Eastern, the zone of MBTA service dates and NOAA's daily weather; timestamps are UTC.
- **Sandboxes:** local work uses `dev_bronze`, `dev_silver`, and `dev_gold`, never the live datasets ([0012](decisions/0012-local-ingest-writes-dev-bronze.md)).
- **Ingest jobs:** `ingest/<source>-<entity>/main.py` writes to `bronze.<source>_<entity>` and runs as the Cloud Run job `ingest-<source>-<entity>`.
- **Alert models** track `first_seen_at` / `last_seen_at` in place of the audit columns, since a row there merges many snapshots.

## Ingest scripts

The docstring lists the job's fields, aligned, then any notes. The body runs in `# ── Fetch ──`, `# ── Shape ──`, and `# ── Load ──` sections:
```text
Source:     MBTA V3 API /shapes (https://api-v3.mbta.com)
Cadence:    Weekly (shapes rarely change)
Each run:   For each rail route, snapshots every shape the API returns
Writes to:  bronze.mbta_shapes (append) — one row per shape × route per run
```
A job that can backfill adds a `Backfill:` field.

Each step logs what it produced, in one form: `Fetched 412 alerts`, `Fetched Red: 22 stations, 140 child stops`, `Shaped 730 rows, 2024-11-01 to 2026-10-31`, `Appended 730 rows to <table>`. A failure goes through `fail()` and names the source and what was wrong: `The MBTA API returned no stops for any rail route`.

## Dashboard

The dashboard's display rules (time windows, statistics, wording, number formats, chart style) are in the header of `serve/app.py`, next to the code that follows them. Its colors and fonts are the design tokens near the top of the same file. Before pushing a change to it, preview it at desktop and phone width (README, [Development & deployment](../README.md#development--deployment)).
