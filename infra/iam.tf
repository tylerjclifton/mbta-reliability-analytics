# ══════════════════════════════════════════════════════════════════════════════
# IAM — least privilege per workload
#
# Data access is granted per dataset, not project-wide. The only project-level
# role a workload gets is bigquery.jobUser (permission to run queries/loads),
# which grants no data access by itself.
#
#                  bronze        silver        gold          other
#   ingest-jobs    dataEditor    —             —             secret: mbta-api-key
#   dbt-bigquery   dataViewer    dataEditor    dataEditor    bigquery.user (dataset lookups)
#   serve-bigquery —             —             dataViewer
#   job-scheduler  —             —             —             run.invoker on each job
# ══════════════════════════════════════════════════════════════════════════════

# ── Project-level ─────────────────────────────────────────────────────────────

locals {
  project_roles = {
    ingest_job_user = { member = google_service_account.ingest.member, role = "roles/bigquery.jobUser" }
    dbt_job_user    = { member = google_service_account.dbt_bigquery.member, role = "roles/bigquery.jobUser" }
    # dbt lists and looks up datasets before building; bigquery.user covers that
    # without granting read or write on any existing dataset
    dbt_user       = { member = google_service_account.dbt_bigquery.member, role = "roles/bigquery.user" }
    serve_job_user = { member = google_service_account.serve_bigquery.member, role = "roles/bigquery.jobUser" }
  }
}

resource "google_project_iam_member" "workload" {
  for_each = local.project_roles

  project = var.project_id
  role    = each.value.role
  member  = each.value.member
}

# ── Dataset-level ─────────────────────────────────────────────────────────────

locals {
  dataset_roles = {
    ingest_writes_bronze = { dataset = google_bigquery_dataset.bronze.dataset_id, role = "roles/bigquery.dataEditor", member = google_service_account.ingest.member }
    dbt_reads_bronze     = { dataset = google_bigquery_dataset.bronze.dataset_id, role = "roles/bigquery.dataViewer", member = google_service_account.dbt_bigquery.member }
    dbt_writes_silver    = { dataset = google_bigquery_dataset.silver.dataset_id, role = "roles/bigquery.dataEditor", member = google_service_account.dbt_bigquery.member }
    dbt_writes_gold      = { dataset = google_bigquery_dataset.gold.dataset_id, role = "roles/bigquery.dataEditor", member = google_service_account.dbt_bigquery.member }
    serve_reads_gold     = { dataset = google_bigquery_dataset.gold.dataset_id, role = "roles/bigquery.dataViewer", member = google_service_account.serve_bigquery.member }
  }
}

resource "google_bigquery_dataset_iam_member" "workload" {
  for_each = local.dataset_roles

  dataset_id = each.value.dataset
  role       = each.value.role
  member     = each.value.member
}

# ── Secret and job-level ──────────────────────────────────────────────────────

# Ingest jobs read the MBTA API key (the secret itself is created by hand)
resource "google_secret_manager_secret_iam_member" "ingest_reads_mbta_api_key" {
  secret_id = "mbta-api-key"
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.ingest.member
}

# The scheduler may start exactly these jobs (run.invoker includes run.jobs.run)
resource "google_cloud_run_v2_job_iam_member" "scheduler_runs_ingest" {
  for_each = google_cloud_run_v2_job.ingest

  name     = each.value.name
  location = each.value.location
  role     = "roles/run.invoker"
  member   = google_service_account.job_scheduler.member
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_runs_transform" {
  name     = google_cloud_run_v2_job.transform.name
  location = google_cloud_run_v2_job.transform.location
  role     = "roles/run.invoker"
  member   = google_service_account.job_scheduler.member
}

# ── Google service agents ─────────────────────────────────────────────────────
# Google grants these when an API is enabled; they're kept here so Terraform
# documents (and would restore) them. Removing one breaks its service.

locals {
  service_agent_roles = {
    cloud_run         = { member = "serviceAccount:${var.default_sa_cloud_run}", role = "roles/run.serviceAgent" }
    artifact_registry = { member = "serviceAccount:${var.default_sa_artifact_registry}", role = "roles/artifactregistry.serviceAgent" }
    cloud_scheduler   = { member = "serviceAccount:${var.default_sa_cloud_scheduler}", role = "roles/cloudscheduler.serviceAgent" }
    # Google APIs service agent: Editor is Google's default for project-level
    # automation (e.g. creating managed resources); not used by our workloads
    google_apis = { member = "serviceAccount:${var.default_sa_google_apis}", role = "roles/editor" }
  }
}

resource "google_project_iam_member" "service_agent" {
  for_each = local.service_agent_roles

  project = var.project_id
  role    = each.value.role
  member  = each.value.member
}

# Pre-refactor addresses of the service-agent grants kept above
moved {
  from = google_project_iam_member.cloud_run_service_agent["roles/run.serviceAgent"]
  to   = google_project_iam_member.service_agent["cloud_run"]
}
moved {
  from = google_project_iam_member.artifact_registry_service_agent["roles/artifactregistry.serviceAgent"]
  to   = google_project_iam_member.service_agent["artifact_registry"]
}
moved {
  from = google_project_iam_member.cloud_scheduler["roles/cloudscheduler.serviceAgent"]
  to   = google_project_iam_member.service_agent["cloud_scheduler"]
}
moved {
  from = google_project_iam_member.google_apis_service_agent["roles/editor"]
  to   = google_project_iam_member.service_agent["google_apis"]
}
moved {
  from = google_project_iam_member.serve_bigquery["roles/bigquery.jobUser"]
  to   = google_project_iam_member.workload["serve_job_user"]
}
moved {
  from = google_project_iam_member.dbt_bigquery["roles/bigquery.jobUser"]
  to   = google_project_iam_member.workload["dbt_job_user"]
}
moved {
  from = google_project_iam_member.dbt_bigquery["roles/bigquery.user"]
  to   = google_project_iam_member.workload["dbt_user"]
}
