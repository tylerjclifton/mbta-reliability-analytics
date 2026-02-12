# Analytics & Data Processing
resource "google_project_service" "analyticshub" {
  service            = "analyticshub.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquery" {
  service            = "bigquery.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquery_connection" {
  service            = "bigqueryconnection.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquery_data_policy" {
  service            = "bigquerydatapolicy.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquery_data_transfer" {
  service            = "bigquerydatatransfer.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquery_migration" {
  service            = "bigquerymigration.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquery_reservation" {
  service            = "bigqueryreservation.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquery_storage" {
  service            = "bigquerystorage.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "dataplex" {
  service            = "dataplex.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "datastore" {
  service            = "datastore.googleapis.com"
  disable_on_destroy = false
}

# Compute & Containers
resource "google_project_service" "artifact_registry" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "container_registry" {
  service            = "containerregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloud_run" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

# Scheduling & Orchestration
resource "google_project_service" "cloud_scheduler" {
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "pubsub" {
  service            = "pubsub.googleapis.com"
  disable_on_destroy = false
}

# Storage
resource "google_project_service" "storage" {
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "storage_api" {
  service            = "storage-api.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "storage_component" {
  service            = "storage-component.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "sql_component" {
  service            = "sql-component.googleapis.com"
  disable_on_destroy = false
}

# Security & IAM
resource "google_project_service" "iam" {
  service            = "iam.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iam_credentials" {
  service            = "iamcredentials.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "secret_manager" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "privileged_access_manager" {
  service            = "privilegedaccessmanager.googleapis.com"
  disable_on_destroy = false
}

# Monitoring & Logging
resource "google_project_service" "logging" {
  service            = "logging.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "monitoring" {
  service            = "monitoring.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloud_trace" {
  service            = "cloudtrace.googleapis.com"
  disable_on_destroy = false
}

# Core GCP Services
resource "google_project_service" "cloud_resource_manager" {
  service            = "cloudresourcemanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "service_management" {
  service            = "servicemanagement.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "service_usage" {
  service            = "serviceusage.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloud_apis" {
  service            = "cloudapis.googleapis.com"
  disable_on_destroy = false
}
