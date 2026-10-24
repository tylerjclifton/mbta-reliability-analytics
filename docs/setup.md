# Setting up a new machine

Everything needed to work on this repo from a fresh computer. Day-to-day commands (running checks, local dbt builds, previewing the dashboard) are in the README's [Development & Deployment](../README.md#development--deployment) section. This page gets you to the point where they work.

## 1. Install the tools

| Tool | Version | Why |
|---|---|---|
| git | any | |
| Google Cloud CLI (`gcloud`, `bq`) | current | Auth, running jobs, querying BigQuery |
| Terraform | **1.14.3** exactly | Matches CI (`.github/workflows/ci.yml`) |
| Python | **3.13** | Matches every image ([0009](decisions/0009-runtime-versions.md)). macOS's built-in `python3` is 3.9 and too old: the tests fail on it |
| Docker Desktop | current | Previewing the dashboard in its production image; running Python 3.13 or dbt without installing them |
| GitHub CLI (`gh`) | optional | Watching CI runs from the terminal |

## 2. Get the code and a Python environment

```bash
git clone https://github.com/tylerjclifton/mbta-reliability-analytics.git
cd mbta-reliability-analytics
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # every component plus ruff, sqlfluff, pytest
```

**No Python 3.13 locally?** Run anything inside a container instead, for example:

```bash
docker run --rm -v "$PWD":/repo -w /repo python:3.13-slim sh -c \
  "pip install -q -r requirements.txt && ruff check ingest serve transform && pytest"
```

## 3. Sign in to Google Cloud

```bash
gcloud auth login                                  # the CLI itself
gcloud config set project mbta-reliability-analytics
gcloud auth application-default login              # credentials for dbt, Terraform, and Python clients
```

Containers that need Google access mount these credentials read-only: `-v ~/.config/gcloud:/root/.config/gcloud:ro -e GOOGLE_CLOUD_PROJECT=mbta-reliability-analytics`.

**gcloud's default project.** This repo's project is `mbta-reliability-analytics`. Other projects get their own GCP project, so use a separate gcloud configuration per project (`gcloud config configurations create <name>`) rather than switching this one.

## 4. Terraform

```bash
cd infra && terraform init        # state lives in GCS (README, "Terraform state")
```

A local plan needs two things CI provides automatically:

```bash
USER_PROJECT_OVERRIDE=true GOOGLE_BILLING_PROJECT=mbta-reliability-analytics \
  terraform plan -var image_tag=$(git rev-parse --short=12 origin/main)
```

- `image_tag` has no default on purpose. Plan against the commit that's deployed ([0006](decisions/0006-deploy-only-through-ci.md)).
- The two environment variables give your local credentials a quota project. Without them, the Cloud Quotas API returns a 403 (`infra/quotas.tf`).
- Don't `apply` locally. Push to `main` and CI applies ([0005](decisions/0005-terraform-only-changes.md), [0006](decisions/0006-deploy-only-through-ci.md)).

## 5. Check that everything works

```bash
ruff check ingest serve transform && pytest                            # Python
(cd transform && dbt parse --profiles-dir . && sqlfluff lint models)   # SQL
(cd infra && terraform fmt -check -recursive && terraform validate)    # Terraform
```

These are the same checks CI runs. If they pass, you're set up.

## Things that live outside the repo

None of these are in code, and some lapsing would take the site down with no alert:

| What | Where | Notes |
|---|---|---|
| **tylerclifton.com** | Squarespace Domains | Expires **2027-08-03**. Keep auto-renew on |
| **GCP billing account** | Cloud Console → Billing | The payment card must stay valid, or the whole project stops |
| **$5/month budget** | Billing → Budgets | Created with `gcloud billing budgets`; alerts only ([0004](decisions/0004-per-query-cost-limits.md)) |
| **MBTA API key value** | Secret Manager, `mbta-api-key` | Terraform owns the secret; the value is added by hand ([runbook](runbook.md#rotate-the-mbta-api-key)) |
| **GitHub `production` environment** | Repo settings → Environments | The deploy job runs in it |
| **Failure-alert email** | `alert_email` in `infra/variables.tf` | In code; listed here so it isn't forgotten |
