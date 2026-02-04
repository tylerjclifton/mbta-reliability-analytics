resource "google_cloud_scheduler_job" "ingestion_alerts" {
  name             = "ingestion-alerts"
  description      = "Job for ingesting MBTA alerts data"
  schedule         = "0 * * * *"
  time_zone        = "UTC"
  attempt_deadline = "5m"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://us-east1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/mbta-reliability-analytics/jobs/ingestion-alerts:run"
    headers = {
      "User-Agent" = "Google-Cloud-Scheduler"
    }
    oidc_token {
      service_account_email = vars.default_sa_compute_engine
      audience              = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

resource "google_cloud_scheduler_job" "ingestion_routes" {
  name             = "ingestion-routes"
  description      = "Job for ingesting MBTA routes data"
  schedule         = "0 * * * *"
  time_zone        = "UTC"
  attempt_deadline = "5m"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://us-east1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/mbta-reliability-analytics/jobs/ingestion-routes:run"
    headers = {
      "User-Agent" = "Google-Cloud-Scheduler"
    }
    oidc_token {
      service_account_email = vars.default_sa_compute_engine
      audience              = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}