# Artifact Registry for Docker Containers
resource "google_artifact_registry_repository" "docker_repo" {
  name         = "data-ingestion"
  location     = var.location
  repository_id = "data-ingestion"
  format       = "DOCKER"
  description  = "Repository for storing Docker images for Cloud Run Jobs"
}

# IAM Role for Artifact Registry Access
resource "google_artifact_registry_repository_iam_member" "artifact_registry_access" {
  repository = google_artifact_registry_repository.docker_repo.id
  role       = "roles/artifactregistry.writer"  # Replace with appropriate role
  member     = "serviceAccount:${google_service_account.cloud_run_sa.email}"  # Replace with your service account
}