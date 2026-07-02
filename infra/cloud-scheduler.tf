resource "google_cloud_scheduler_job" "ingest_alerts" {
  name             = "ingest-mbta-alerts"
  schedule         = var.ingestion_schedule
  time_zone        = var.scheduler_time_zone
  attempt_deadline = "180s"
  paused           = false

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.location}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.location}/jobs/ingest-mbta-alerts:run"
    oauth_token {
      service_account_email = var.default_sa_compute_engine
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

resource "google_cloud_scheduler_job" "ingest_routes" {
  name             = "ingest-mbta-routes"
  schedule         = "0 0 1 1,4,7,10 *"
  time_zone        = var.scheduler_time_zone
  attempt_deadline = "180s"
  paused           = false

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.location}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.location}/jobs/ingest-mbta-routes:run"
    oauth_token {
      service_account_email = var.default_sa_compute_engine
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

resource "google_cloud_scheduler_job" "ingest_weather" {
  name             = "ingest-nws-weather"
  schedule         = var.ingestion_schedule
  time_zone        = var.scheduler_time_zone
  attempt_deadline = "180s"
  paused           = false

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.location}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.location}/jobs/ingest-nws-weather:run"
    oauth_token {
      service_account_email = var.default_sa_compute_engine
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

resource "google_cloud_scheduler_job" "transform_pipeline" {
  name             = "transform"
  schedule         = var.transform_schedule
  time_zone        = var.scheduler_time_zone
  attempt_deadline = "600s" # 10 minutes deadline for dbt
  paused           = false

  retry_config {
    retry_count = 1 # Retry once if it fails
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.location}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.location}/jobs/transform:run"
    oauth_token {
      service_account_email = google_service_account.dbt_bigquery.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}