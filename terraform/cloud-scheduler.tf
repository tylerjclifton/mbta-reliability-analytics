resource "google_cloud_scheduler_job" "ingestion_alerts" {
  name             = "ingestion-alerts"
  schedule         = "0 * * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "180s"
  paused           = false

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://us-east1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/mbta-reliability-analytics/jobs/ingestion-alerts:run"
    oauth_token {
      service_account_email = var.default_sa_compute_engine
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

resource "google_cloud_scheduler_job" "ingestion_routes" {
  name             = "ingestion-routes"
  schedule         = "0 0 1 1,4,7,10 *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "180s"
  paused           = false

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://us-east1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/mbta-reliability-analytics/jobs/ingestion-routes:run"
    oauth_token {
      service_account_email = var.default_sa_compute_engine
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

resource "google_cloud_scheduler_job" "dbt_transform" {
  name             = "dbt-transform"
  schedule         = "10 * * * *"  # Runs at :10 past each hour (after ingestion)
  time_zone        = "Etc/UTC"
  attempt_deadline = "600s"  # 10 minutes deadline for dbt
  paused           = false

  retry_config {
    retry_count = 1  # Retry once if it fails
  }

  http_target {
    http_method = "POST"
    uri         = "https://us-east1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/mbta-reliability-analytics/jobs/dbt-transform:run"
    oauth_token {
      service_account_email = var.default_sa_compute_engine
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}