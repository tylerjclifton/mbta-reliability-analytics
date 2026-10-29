# CLAUDE.md

Guidance for AI coding sessions in this repo. Humans: the same docs apply.

**Read first:** [README.md](README.md) (architecture, conventions), [docs/decisions/](docs/decisions/README.md) (why things are the way they are), [docs/roadmap.md](docs/roadmap.md) (what's planned), [docs/setup.md](docs/setup.md), and [docs/runbook.md](docs/runbook.md).

## Rules
- **Bronze is append-only.** Never update, delete, or rebuild bronze rows or tables ([0001](docs/decisions/0001-append-only-bronze.md)).
- **Infrastructure changes go through Terraform only**: edit `infra/`, plan locally, push ([0005](docs/decisions/0005-terraform-only-changes.md)).
- **Deploy by pushing to `main`**; CI builds, applies, and runs the transform ([0006](docs/decisions/0006-deploy-only-through-ci.md)). Watch the run and confirm it passed.
- **Adding a source:** push the ingest and tables first, seed them, then push the models that read them, so the post-deploy freshness check doesn't fail on empty tables.
- **Docs change with the code**, in the same commit: README, dbt model headers and yml, `docs/`. Record new decisions in `docs/decisions/`.
- **Commits carry no AI co-author trailer** or "Generated with" line.
- **Comment generously**: every model and script gets a header with its purpose, grain, and steps; follow the naming conventions in the README.

## Local environment
- Python 3.13 (the system `python3` on macOS is 3.9 and too old). Without it, run checks in `python:3.13-slim` via Docker ([setup](docs/setup.md)).
- Local `terraform plan`: `USER_PROJECT_OVERRIDE=true GOOGLE_BILLING_PROJECT=mbta-reliability-analytics terraform plan -var image_tag=$(git rev-parse --short=12 origin/main)`.
- Local dbt (`--target local`) writes only to `dev_silver` / `dev_gold`. Test model changes there against live bronze before pushing.
- A local ingest run writes to `dev_bronze`, never production bronze ([0012](docs/decisions/0012-local-ingest-writes-dev-bronze.md)). Real bronze is written only by the Cloud Run jobs.
