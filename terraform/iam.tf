# Artifact Registry Service Agent
resource "google_project_iam_binding" "roles_artifactregistry_service_agent" {
  project = var.project_id
  role    = "roles/artifactregistry.serviceAgent"
  members = [
    "serviceAccount:${var.default_sa_artifact_registry}"
  ]
}

# BigQuery Admin
resource "google_project_iam_binding" "roles_bigquery_admin" {
  project = var.project_id
  role    = "roles/bigquery.admin"
  members = [
    "serviceAccount:${service-accounts.custom_sa_terraform_runner}"
  ]
}

# BigQuery Data Editor
resource "google_project_iam_binding" "roles_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  members = [
    "serviceAccount:${var.default_sa_dataform}"
  ]
}

# BigQuery Data Transfer Service Agent
resource "google_project_iam_binding" "roles_bigquery_data_transfer_service_agent" {
  project = var.project_id
  role    = "roles/bigquery.admin"
  members = [
    "serviceAccount:${var.default_sa_bigquery_data_transfer}"
  ]
}

# BigQuery Job User
 resource "google_project_iam_binding" "roles_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  members = [
    "serviceAccount:${var.default_sa_compute_engine}",
    "serviceAccount:${var.default_sa_dataform}"
  ]
}

# BigQuery User
 resource "google_project_iam_binding" "roles_bigquery_user" {
  project = var.project_id
  role    = "roles/bigquery.user"
  members = [
    "serviceAccount:${var.default_sa_dataform}"
  ]
}

# Cloud Pub/Sub Service Agent
 resource "google_project_iam_binding" "roles_cloud_pubsub_service_agent" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${var.default_sa_cloud_pubsub}"
  ]
}

# Cloud Run Developer
 resource "google_project_iam_binding" "roles_cloud_run_developer" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${var.default_sa_compute_engine}"
  ]
}

# Cloud Run Invoker
 resource "google_project_iam_binding" "roles_cloud_run_invoker" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${var.default_sa_compute_engine}",
    "serviceAccount:${var.default_sa_cloud_scheduler}"
  ]
}

# Cloud Run Service Agent
 resource "google_project_iam_binding" "roles_cloud_run_service_agent" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${var.default_sa_cloud_run}"
  ]
}

# Cloud Scheduler Service Agent
 resource "google_project_iam_binding" "roles_cloud_scheduler_service_agent" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${var.default_sa_compute_engine}",
    "serviceAccount:${var.default_sa_cloud_scheduler}"
  ]
}

# Compute Admin
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${service-accounts.custom_sa_terraform_runner}"
  ]
}

# Container Registry Service Agent
 resource "google_project_iam_binding" "roles_container_registry_service_agent" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${var.default_sa_google_container_registry}"
  ]
}

# Dataform Service Agent
 resource "google_project_iam_binding" "roles_dataform_service_agent" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${var.default_sa_dataform}"
  ]
}

# Editor
 resource "google_project_iam_binding" "roles_editor" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${var.default_sa_compute_engine}",
    "serviceAccount:${var.default_sa_google_apis}",
    "serviceAccount:${var.default_sa_dataform}"
  ]
}

# Secret Manager Secret Accessor
 resource "google_project_iam_binding" "roles_secretmanager_secret_accessor" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${var.default_sa_dataform}"
  ]
}

# Secret Account Token Creator
 resource "google_project_iam_binding" "roles_secretmanager_secret_account_token_creator" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${var.default_sa_compute_engine}",
    "serviceAccount:${var.default_sa_dataform}"
  ]
}

# Secret Account User
 resource "google_project_iam_binding" "roles_secret_account_user" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${var.default_sa_dataform}"
  ]
}

# Storage Admin
 resource "google_project_iam_binding" "roles_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.custom_sa_terraform_runner.email}"
  ]
}