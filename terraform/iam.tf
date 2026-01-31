# Artifact Registry Service Agent
resource "google_project_iam_binding" "roles_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:558105773739-compute@developer.gserviceaccount.com"
  ]
}

# BigQuery Admin
resource "google_project_iam_binding" "roles_bigquery_admin" {
  project = var.project_id
  role    = "roles/bigquery.admin"
  members = [
    "serviceAccount:558105773739-compute@developer.gserviceaccount.com"
  ]
}

# BigQuery Data Editor
resource "google_project_iam_binding" "roles_compute_admin" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  members = [
    "serviceAccount:558105773739-compute@developer.gserviceaccount.com"
  ]
}

# BigQuery Data Transfer Service Agent
resource "google_project_iam_binding" "terraform_runner_sa_bigquery_admin" {
  project = var.project_id
  role    = "roles/bigquery.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# BigQuery Job User
 resource "google_project_iam_binding" "terraform_runner_sa_compute_admin" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# BigQuery User
 resource "google_project_iam_binding" "terraform_runner_sa_compute_admin" {
  project = var.project_id
  role    = "roles/compute.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Cloud Pub/Sub Service Agent
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Cloud Run Developer
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Cloud Run Invoker
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Cloud Run Service Agent
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Cloud Scheduler Service Agent
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Compute Admin
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Container Registry Service Agent
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Dataform Service Agent
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Editor
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Owner
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Secret Manager Secret Accessor
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Secret Account Token Creator
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Secret Account User
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}

# Storage Admin
 resource "google_project_iam_binding" "terraform_runner_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.terraform_runner_sa.email}"
  ]
}