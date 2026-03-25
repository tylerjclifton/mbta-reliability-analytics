resource "google_cloud_run_v2_job" "ingestion_alerts" {
  name     = "mbta-ingestion-alerts"
  location = var.location

  deletion_protection = false

  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      service_account = var.default_sa_compute_engine
      containers {
        name  = "mbta-ingestion-alerts"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/mbta-ingestion-alerts:latest"
        env {
          name  = "BQ_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "BQ_DATASET_ID"
          value = "staging"
        }
        env {
          name  = "BQ_TABLE_ID"
          value = "mbta_alerts"
        }
        resources {
          limits = {
            memory = "512Mi"
            cpu    = "1000m"
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "ingestion_routes" {
  name     = "mbta-ingestion-routes"
  location = var.location

  deletion_protection = false

  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      service_account = var.default_sa_compute_engine
      containers {
        name  = "mbta-ingestion-routes"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/mbta-ingestion-routes:latest"
        env {
          name  = "BQ_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "BQ_DATASET_ID"
          value = "staging"
        }
        env {
          name  = "BQ_TABLE_ID"
          value = "mbta_routes"
        }
        resources {
          limits = {
            memory = "512Mi"
            cpu    = "1000m"
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "ingestion_weather" {
  name     = "nws-ingestion-weather"
  location = var.location

  deletion_protection = false

  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      service_account = var.default_sa_compute_engine
      containers {
        name  = "nws-ingestion-weather"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/nws-ingestion-weather:latest"
        env {
          name  = "BQ_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "BQ_DATASET_ID"
          value = "staging"
        }
        env {
          name  = "BQ_TABLE_ID"
          value = "nws_weather"
        }
        resources {
          limits = {
            memory = "512Mi"
            cpu    = "1000m"
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "dbt_transform" {
  name     = "mbta-transform"
  location = var.location

  deletion_protection = false

  template {
    task_count  = 1
    parallelism = 0
    template {
      service_account = google_service_account.dbt_bigquery.email
      containers {
        name  = "mbta-transform"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/mbta-transform:latest"
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
      timeout = "600s" # 10 minutes for dbt to complete
    }
  }
}