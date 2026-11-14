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
  # name with "-" for "_" (e.g. mbta-alerts → bronze.mbta_alerts). A null
  # schedule means the job runs only on demand (docs/runbook.md). Two optional
  # fields, for renames (runbook, "Rename a bronze table"): `table` points a
  # job at a table of another name, and `deletion_protection = false` lets
  # the next apply destroy the job.
  ingest_jobs = {
    "lamp-alerts" = {
      schedule          = var.lamp_ingestion_schedule
      uses_mbta_api_key = false
      memory            = "2Gi" # reads the whole 5M+ row file, in batches sized for it (ingest/lamp-alerts/main.py)
      timeout           = "1800s"
      env               = {}
    }
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
    "mbta-shapes" = {
      schedule          = var.shapes_ingestion_schedule
      uses_mbta_api_key = true
      memory            = "512Mi"
      timeout           = "600s" # Seven requests, one per route
      env               = {}
    }
    "mbta-stops" = {
      schedule          = var.stops_ingestion_schedule
      uses_mbta_api_key = true
      memory            = "512Mi"
      timeout           = "600s" # Seven requests, one per route
      env               = {}
    }
    "mbta-commuter-rail-boardings" = {
      schedule          = var.commuter_rail_boardings_ingestion_schedule
      uses_mbta_api_key = false
      memory            = "512Mi"
      timeout           = "600s" # One file, under 1 MB
      env               = {}
    }
    "mbta-ferry-trips" = {
      schedule          = var.ferry_ingestion_schedule
      uses_mbta_api_key = false
      memory            = "2Gi" # the whole layer (~400K rows) on a backfill
      timeout           = "1200s"
      # Re-pulls LOOKBACK_DAYS days of service each run; the default, 365, is
      # set once in ingest/mbta-ferry-trips/main.py. Override it at execution
      # time to backfill: `--update-env-vars LOOKBACK_DAYS=4000`.
      env = {}
    }
    "mbta-monthly-ridership" = {
      schedule          = var.monthly_ridership_ingestion_schedule
      uses_mbta_api_key = false
      memory            = "512Mi"
      timeout           = "600s" # The whole layer, ~5,000 rows
      env               = {}
    }
    "mbta-gated-entries" = {
      schedule          = var.gated_entries_ingestion_schedule
      uses_mbta_api_key = false
      memory            = "1Gi"
      timeout           = "900s" # The layer's two years, paged; or the yearly archive
      env               = {}
    }
    "noaa-weather" = {
      schedule          = var.weather_ingestion_schedule
      uses_mbta_api_key = false
      memory            = "512Mi"
      timeout           = "600s"
      # Re-pulls LOOKBACK_DAYS days each run (NOAA revises recent days); the
      # default, 10, is set once in ingest/noaa-weather/main.py. Override it at
      # execution time to backfill: `--update-env-vars LOOKBACK_DAYS=800`.
      env = {}
    }
  }
}

# ── Ingest jobs ───────────────────────────────────────────────────────────────

resource "google_cloud_run_v2_job" "ingest" {
  for_each = local.ingest_jobs

  name     = "ingest-${each.key}"
  location = var.location

  # On, unless a job sets deletion_protection = false to be retired: Terraform
  # can't destroy a protected job (docs/runbook.md, "Rename a bronze table").
  deletion_protection = try(each.value.deletion_protection, true)

  # Cloud Run checks secret access when the job is updated, so the ingest
  # account's grant on the MBTA API key must exist first.
  depends_on = [google_secret_manager_secret_iam_member.ingest_reads_mbta_api_key]

  template {
    # One task per execution (parallelism 0 means no limit, moot with one task).
    task_count  = 1
    parallelism = 0
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
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        # Production bronze. Set explicitly because a run without it (a local
        # one) writes to dev_bronze instead (decision 0012).
        env {
          name  = "BQ_DATASET_ID"
          value = google_bigquery_dataset.bronze.dataset_id
        }
        # The job's own table, unless it names another (`table`). Looked up,
        # not just named, so a plan fails if the table doesn't exist.
        env {
          name  = "BQ_TABLE_ID"
          value = google_bigquery_table.bronze[try(each.value.table, replace(each.key, "-", "_"))].table_id
        }

        # Job-specific settings.
        dynamic "env" {
          for_each = each.value.env
          content {
            name  = env.key
            value = env.value
          }
        }

        # MBTA API key (optional for the API, but
        # removes the anonymous rate limit).
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
    # One task per execution (parallelism 0 means no limit, moot with one task).
    task_count  = 1
    parallelism = 0
    template {
      service_account = google_service_account.dbt_bigquery.email
      timeout         = "600s" # 10 minutes for dbt build + freshness
      max_retries     = local.transform_max_retries
      containers {
        name  = "transform"
        image = "${local.backend_registry}/transform:${var.image_tag}"
        env {
          name  = "MAX_RETRIES"
          value = tostring(local.transform_max_retries)
        }
        env {
          name  = "GCP_PROJECT_ID"
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
