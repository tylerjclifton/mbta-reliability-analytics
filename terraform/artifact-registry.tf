# Artifact Registry for Docker Containers
resource "google_artifact_registry_repository" "data-ingestion" {
  name         = "data-ingestion"
  location     = var.location
  repository_id = "data-ingestion"
  format       = "DOCKER"
  description  = "Repository for storing Docker images for Cloud Run Jobs"
}

# IAM Role for Artifact Registry Access
resource "google_artifact_registry_repository_iam_member" "artifact_registry_access" {
  repository = google_artifact_registry_repository.data-ingestion.id
  role       = "roles/artifactregistry.admin"
  member     = "serviceAccount:${google_service_account.cloud_run_sa.email}"  # Replace with your service account
}