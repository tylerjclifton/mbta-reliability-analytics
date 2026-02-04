# Artifact Registry for Docker Containers
resource "google_artifact_registry_repository" "data-ingestion" {
  name         = "data-ingestion"
  location     = var.location
  repository_id = "data-ingestion"
  format       = "DOCKER"
  description  = "Repository for storing Docker images for Cloud Run Jobs"
}