# Streamlit dashboard served publicly via Cloud Run
resource "google_cloud_run_v2_service" "serve" {
  name     = "serve"
  location = var.location

  deletion_protection = false

  template {
    service_account = google_service_account.serve_bigquery.email

    containers {
      name  = "serve"
      image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/frontend/serve:v1.2.7"

      ports {
        container_port = 8080
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      resources {
        limits = {
          memory = "512Mi"
          cpu    = "1000m"
        }
        cpu_idle = true # Scale to zero when no traffic (keeps costs near zero)
      }
    }

    scaling {
      min_instance_count = 0 # Allow scale-to-zero
      max_instance_count = 2 # Cap instances for cost control
    }
  }
}

# Allow unauthenticated public access (portfolio site)
resource "google_cloud_run_v2_service_iam_member" "serve_public" {
  project  = var.project_id
  location = var.location
  name     = google_cloud_run_v2_service.serve.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Custom domain mapping — tylerclifton.com (canonical, no www)
resource "google_cloud_run_domain_mapping" "serve_domain" {
  location = var.location
  name     = var.serve_domain

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.serve.name
  }
}

# www.tylerclifton.com also mapped — Cloud Run will redirect to canonical
resource "google_cloud_run_domain_mapping" "serve_domain_www" {
  location = var.location
  name     = "www.${var.serve_domain}"

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.serve.name
  }
}
