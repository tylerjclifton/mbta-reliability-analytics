# ══════════════════════════════════════════════════════════════════════════════
# Cloud Run jobs — ingest (one per source) and transform (dbt)
#
# All ingest jobs run the same image (ingest/Dockerfile); each job runs its own
# script via container args and appends to its bronze table of the same name.
# ══════════════════════════════════════════════════════════════════════════════

locals {
  backend_registry = "${var.location}-docker.pkg.dev/${var.project_id}/backend"

  # Retries per failed task. Each job also receives its value as MAX_RETRIES, so
  # only the final attempt's failure report triggers an alert (monitoring.tf).
  #   ingest     one retry absorbs transient API errors
  #   transform  none: dbt retries BigQuery errors itself, and a failed test or
  #              freshness check won't pass on retry
  ingest_max_retries    = 1
  transform_max_retries = 0

  # One entry per ingest job. Key = job folder under ingest/ = bronze table
  # name with "-" for "_" (e.g. mbta-alerts → bronze.mbta_alerts).
  ingest_jobs = {
    "mbta-alerts" = {
      schedule          = var.alerts_ingestion_schedule
      uses_mbta_api_key = true
      memory            = "512Mi"
      timeout           = "600s"
      env               = {}
    }
    "mbta-routes" = {
      schedule          = var.routes_ingestion_schedule
      uses_mbta_api_key = true
      memory            = "512Mi"
      timeout           = "600s"
      env               = {}
    }
    "mbta-ridership" = {
      schedule          = var.ridership_ingestion_schedule
      uses_mbta_api_key = false
      memory            = "1Gi"
      timeout           = "900s" # Full-history ArcGIS pull, several paginated requests
      env               = {}
    }
    "noaa-weather" = {
      schedule          = var.weather_ingestion_schedule
      uses_mbta_api_key = false
      memory            = "512Mi"
      timeout           = "600s"
      env = {
        # Days re-pulled each run (NOAA revises recent days). Override at
        # execution time to backfill: --update-env-vars LOOKBACK_DAYS=800
        LOOKBACK_DAYS = "10"
      }
    }
  }
}

# ── Ingest jobs ───────────────────────────────────────────────────────────────

resource "google_cloud_run_v2_job" "ingest" {
  for_each = local.ingest_jobs

  name     = "ingest-${each.key}"
  location = var.location

  deletion_protection = true

  # Cloud Run checks secret access when the job is updated, so the ingest
  # account's grant on the MBTA API key must exist first
  depends_on = [google_secret_manager_secret_iam_member.ingest_reads_mbta_api_key]

  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      service_account = google_service_account.ingest.email
      timeout         = each.value.timeout
      max_retries     = local.ingest_max_retries

      containers {
        name  = "ingest-${each.key}"
        image = "${local.backend_registry}/ingest:${var.image_tag}"
        args  = ["${each.key}/main.py"]

        env {
          name  = "MAX_RETRIES"
          value = tostring(local.ingest_max_retries)
        }
        env {
          name  = "BQ_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "BQ_DATASET_ID"
          value = google_bigquery_dataset.bronze.dataset_id
        }
        env {
          name  = "BQ_TABLE_ID"
          value = google_bigquery_table.bronze[replace(each.key, "-", "_")].table_id
        }

        # Job-specific settings
        dynamic "env" {
          for_each = each.value.env
          content {
            name  = env.key
            value = env.value
          }
        }

        # MBTA API key (optional for the API, but removes the anonymous rate limit)
        dynamic "env" {
          for_each = each.value.uses_mbta_api_key ? [1] : []
          content {
            name = "MBTA_API_KEY"
            value_source {
              secret_key_ref {
                secret  = "mbta-api-key"
                version = "latest"
              }
            }
          }
        }

        resources {
          limits = {
            memory = each.value.memory
            cpu    = "1000m"
          }
        }
      }
    }
  }
}

# ── Transform job ─────────────────────────────────────────────────────────────

resource "google_cloud_run_v2_job" "transform" {
  name     = "transform"
  location = var.location

  deletion_protection = true

  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      service_account = google_service_account.dbt_bigquery.email
      timeout         = "600s" # 10 minutes for dbt to complete
      max_retries     = local.transform_max_retries
      containers {
        name  = "transform"
        image = "${local.backend_registry}/transform:${var.image_tag}"
        env {
          name  = "MAX_RETRIES"
          value = tostring(local.transform_max_retries)
        }
        env {
          name  = "DBT_PROJECT_ID"
          value = var.project_id
        }
        resources {
          limits = {
            memory = "1Gi"
            cpu    = "2000m"
          }
        }
      }
    }
  }
}
