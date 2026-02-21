# Artifact Registry for Docker Containers
resource "google_artifact_registry_repository" "data_ingestion" {
  location      = var.location
  repository_id = "data-ingestion"
  format        = "DOCKER"
  description   = "MBTA data ingestion Docker images"
}