# Artifact Registry for backend containers
resource "google_artifact_registry_repository" "backend" {
  location      = var.location
  repository_id = "backend"
  format        = "DOCKER"
  description   = "MBTA backend Docker images"
}

# Artifact Registry for frontend containers
resource "google_artifact_registry_repository" "frontend" {
  location      = var.location
  repository_id = "frontend"
  format        = "DOCKER"
  description   = "MBTA frontend Docker images"
}