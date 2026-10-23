# ══════════════════════════════════════════════════════════════════════════════
# Google APIs the project uses
#
# Only what the pipeline needs. Unused APIs from the default "Google Cloud APIs"
# bundle (Dataplex, Datastore, Analytics Hub, BigQuery Data Transfer, …) were
# disabled in 2026-10. disable_on_destroy = false everywhere: removing an entry
# here stops Terraform managing it but never switches the API off underneath a
# running service.
#
# Enabled outside Terraform and deliberately left alone: Cloud Build (and Pub/Sub,
# which it requires) and the Gemini console assistants.
# ══════════════════════════════════════════════════════════════════════════════

locals {
  project_apis = {
    # Data
    bigquery         = "bigquery.googleapis.com"        # warehouse (bronze/silver/gold)
    bigquery_storage = "bigquerystorage.googleapis.com" # fast table reads; required by BigQuery

    # Compute + scheduling
    run             = "run.googleapis.com"            # ingest/transform jobs, dashboard service
    cloud_scheduler = "cloudscheduler.googleapis.com" # cron triggers
    cloud_trace     = "cloudtrace.googleapis.com"     # required by Cloud Scheduler

    # Cost guardrails (the budget itself lives on the billing account, outside Terraform)
    billing_budgets = "billingbudgets.googleapis.com"
    cloud_quotas    = "cloudquotas.googleapis.com" # BigQuery daily query quota (quotas.tf)

    # Images + secrets
    artifact_registry = "artifactregistry.googleapis.com" # Docker images
    secret_manager    = "secretmanager.googleapis.com"    # MBTA API key

    # Storage (Terraform state bucket)
    storage           = "storage.googleapis.com"
    storage_api       = "storage-api.googleapis.com"
    storage_component = "storage-component.googleapis.com"

    # Identity, logging, and platform plumbing
    iam                    = "iam.googleapis.com"
    iam_credentials        = "iamcredentials.googleapis.com" # short-lived tokens (Scheduler → Run, GitHub → deployer)
    sts                    = "sts.googleapis.com"            # exchanges GitHub OIDC tokens (deploy.tf)
    logging                = "logging.googleapis.com"
    monitoring             = "monitoring.googleapis.com"
    cloud_resource_manager = "cloudresourcemanager.googleapis.com"
    service_management     = "servicemanagement.googleapis.com"
    service_usage          = "serviceusage.googleapis.com"
  }
}

resource "google_project_service" "api" {
  for_each = local.project_apis

  service            = each.value
  disable_on_destroy = false
}
