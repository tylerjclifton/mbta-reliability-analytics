# Artifact Registry for backend pipeline containers (ingestion + transform)
resource "google_artifact_registry_repository" "backend" {
  location      = var.location
  repository_id = "backend"
  format        = "DOCKER"
  description   = "MBTA backend pipeline Docker images (ingestion + transform)"
}

# Artifact Registry for frontend containers
resource "google_artifact_registry_repository" "frontend" {
  location      = var.location
  repository_id = "frontend"
  format        = "DOCKER"
  description   = "MBTA frontend Docker images"
}