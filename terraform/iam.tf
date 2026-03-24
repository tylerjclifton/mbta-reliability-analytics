# Terraform Runner Service Account Roles
locals {
  terraform_runner_roles = [
    "roles/artifactregistry.admin",
    "roles/bigquery.admin",
    "roles/run.admin",
    "roles/compute.admin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/storage.admin"
  ]
}

resource "google_project_iam_member" "terraform_runner" {
  for_each = toset(local.terraform_runner_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.terraform_runner.email}"
}

# Default Compute Engine Service Account Roles
locals {
  compute_engine_roles = [
    "roles/bigquery.jobUser",
    "roles/run.developer",
    "roles/run.invoker",
    "roles/cloudscheduler.serviceAgent",
    "roles/editor",
    "roles/iam.serviceAccountTokenCreator",
    "roles/iam.serviceAccountUser"
  ]
}

resource "google_project_iam_member" "compute_engine" {
  for_each = toset(local.compute_engine_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.default_sa_compute_engine}"
}

# Default Dataform Service Account Roles
locals {
  dataform_roles = [
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/bigquery.user",
    "roles/dataform.serviceAgent",
    "roles/editor",
    "roles/secretmanager.secretAccessor",
    "roles/iam.serviceAccountTokenCreator",
    "roles/iam.serviceAccountUser"
  ]
}

resource "google_project_iam_member" "dataform" {
  for_each = toset(local.dataform_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.default_sa_dataform}"
}

# Default Cloud Scheduler Service Account Roles
locals {
  cloud_scheduler_roles = [
    "roles/run.invoker",
    "roles/cloudscheduler.serviceAgent"
  ]
}

resource "google_project_iam_member" "cloud_scheduler" {
  for_each = toset(local.cloud_scheduler_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.default_sa_cloud_scheduler}"
}

# Artifact Registry Service Agent Roles
locals {
  artifact_registry_service_agent_roles = [
    "roles/artifactregistry.serviceAgent"
  ]
}

resource "google_project_iam_member" "artifact_registry_service_agent" {
  for_each = toset(local.artifact_registry_service_agent_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.default_sa_artifact_registry}"
}

# dbt BigQuery Service Account Roles
locals {
  dbt_bigquery_roles = [
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/bigquery.user"
  ]
}

resource "google_project_iam_member" "dbt_bigquery" {
  for_each = toset(local.dbt_bigquery_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.dbt_bigquery.email}"
}

# BigQuery Data Transfer Service Agent Roles
locals {
  bigquery_data_transfer_service_agent_roles = [
    "roles/bigquerydatatransfer.serviceAgent"
  ]
}

resource "google_project_iam_member" "bigquery_data_transfer_service_agent" {
  for_each = toset(local.bigquery_data_transfer_service_agent_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.default_sa_bigquery_data_transfer}"
}

# Cloud Pub/Sub Service Agent Roles
locals {
  cloud_pubsub_service_agent_roles = [
    "roles/pubsub.serviceAgent"
  ]
}

resource "google_project_iam_member" "cloud_pubsub_service_agent" {
  for_each = toset(local.cloud_pubsub_service_agent_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.default_sa_cloud_pubsub}"
}

# Cloud Run Service Agent Roles
locals {
  cloud_run_service_agent_roles = [
    "roles/run.serviceAgent"
  ]
}

resource "google_project_iam_member" "cloud_run_service_agent" {
  for_each = toset(local.cloud_run_service_agent_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.default_sa_cloud_run}"
}

# Container Registry Service Agent Roles
locals {
  container_registry_service_agent_roles = [
    "roles/containerregistry.ServiceAgent"
  ]
}

resource "google_project_iam_member" "container_registry_service_agent" {
  for_each = toset(local.container_registry_service_agent_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.default_sa_google_container_registry}"
}

# Google APIs Service Agent Roles
locals {
  google_apis_service_agent_roles = [
    "roles/editor"
  ]
}

resource "google_project_iam_member" "google_apis_service_agent" {
  for_each = toset(local.google_apis_service_agent_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.default_sa_google_apis}"
}