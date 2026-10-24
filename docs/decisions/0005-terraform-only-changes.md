# 0005 — Every infrastructure change goes through Terraform

**Status:** Accepted · **Date:** 2026-10-23

## Context
During the quota incident ([0004](0004-per-query-cost-limits.md)), the quota was changed with `gcloud` to test a fix before the Terraform was pushed. GCP and code disagreed, and the next deploy would have silently reverted the change.

## Decision
- Change GCP resources only by editing `infra/`, running a local plan, and pushing ([0006](0006-deploy-only-through-ci.md)). No console or `gcloud … update` changes to managed resources, even as an experiment.
- If an urgent fix truly needs an out-of-band change, agree on it first and bring Terraform in line in the same session.
- Exceptions by design, documented where they live: secret *values* (`infra/secrets.tf`) and the billing budget ([0004](0004-per-query-cost-limits.md)).

## Consequences
- `terraform plan` against production should show no drift. Treat any drift as a bug.
- Local plans need the setup in [setup.md](../setup.md) (image tag plus the quota-project variables).
