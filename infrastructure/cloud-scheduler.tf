resource "google_cloud_scheduler_job" "ingestion_alerts" {
  name             = "mbta-ingestion-alerts"
  schedule         = "0 */6 * * *" # Every 6 hours at minute 0
  time_zone        = "Etc/UTC"
  attempt_deadline = "180s"
  paused           = false

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.location}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.location}/jobs/ingestion-mbta-alerts:run"
    oauth_token {
      service_account_email = var.default_sa_compute_engine
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

resource "google_cloud_scheduler_job" "ingestion_routes" {
  name             = "mbta-ingestion-routes"
  schedule         = "0 0 1 1,4,7,10 *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "180s"
  paused           = false

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.location}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.location}/jobs/ingestion-mbta-routes:run"
    oauth_token {
      service_account_email = var.default_sa_compute_engine
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

resource "google_cloud_scheduler_job" "ingestion_weather" {
  name             = "nws-ingestion-weather"
  schedule         = "0 */6 * * *" # Every 6 hours at minute 0 (same as alerts)
  time_zone        = "Etc/UTC"
  attempt_deadline = "180s"
  paused           = false

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.location}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.location}/jobs/ingestion-nws-weather:run"
    oauth_token {
      service_account_email = var.default_sa_compute_engine
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

resource "google_cloud_scheduler_job" "transform_pipeline" {
  name             = "transform-pipeline"
  schedule         = "10 */6 * * *" # Every 6 hours at minute 10 (after ingestion)
  time_zone        = "Etc/UTC"
  attempt_deadline = "600s" # 10 minutes deadline for dbt
  paused           = false

  retry_config {
    retry_count = 1 # Retry once if it fails
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.location}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.location}/jobs/transform-pipeline:run"
    oauth_token {
      service_account_email = google_service_account.dbt_bigquery.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}