# CLAUDE.md

Guidance for AI coding sessions in this repo. Everything here is a summary; the linked docs have the detail and apply to humans too.

**Read first:** [README.md](README.md) (architecture), [docs/conventions.md](docs/conventions.md) (naming, comments, docs, commits), [docs/decisions/](docs/decisions/README.md) (why things are the way they are), [docs/setup.md](docs/setup.md) (local environment), [docs/runbook.md](docs/runbook.md) (operational tasks), and [docs/roadmap.md](docs/roadmap.md) (what's planned).

## Guardrails
Mistakes here are hard or impossible to undo.
- **Bronze is append-only.** Never update, delete, or rebuild bronze rows or tables, and never write production bronze from a local run: local ingest goes to `dev_bronze` ([0001](docs/decisions/0001-append-only-bronze.md), [0012](docs/decisions/0012-local-ingest-writes-dev-bronze.md)).
- **Never let Terraform replace a bronze table.** Check every plan for one. Renames follow the runbook's BigQuery rename plus `import` procedure; removing a column, changing a type, or changing partitioning isn't done ([0013](docs/decisions/0013-bronze-tables-in-terraform.md)).
- **Infrastructure changes go through Terraform only**: edit `infra/`, plan locally, push ([0005](docs/decisions/0005-terraform-only-changes.md)).
- **Deploy by pushing to `main`**; CI builds, applies, and runs the transform ([0006](docs/decisions/0006-deploy-only-through-ci.md)). Watch the run and confirm it passed.
- **Adding a source:** push the ingest and its table first, seed it, then push the models that read it, so the post-deploy freshness check doesn't fail on an empty table ([runbook](docs/runbook.md#add-a-new-source)).
- **Test model changes locally first**: `--target local` builds into `dev_silver` / `dev_gold` against live bronze.

## Working in this repo
- Follow [docs/conventions.md](docs/conventions.md) for naming, file headers, comments, docs, and commit messages.
- Commits carry no AI co-author trailer or "Generated with" line.
- macOS's system `python3` is 3.9 and too old; use Python 3.13, or run the checks in `python:3.13-slim` via Docker ([setup](docs/setup.md)). The local `terraform plan` command is in setup, step 4.
