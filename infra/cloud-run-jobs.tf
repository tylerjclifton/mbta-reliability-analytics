resource "google_cloud_run_v2_job" "ingest_mbta_alerts" {
  name     = "ingest-mbta-alerts"
  location = var.location

  deletion_protection = false

  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      service_account = var.default_sa_compute_engine
      containers {
        name  = "ingest-mbta-alerts"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/backend/ingest-mbta-alerts:v1.0.0"
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

resource "google_cloud_run_v2_job" "ingest_mbta_routes" {
  name     = "ingest-mbta-routes"
  location = var.location

  deletion_protection = false

  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      service_account = var.default_sa_compute_engine
      containers {
        name  = "ingest-mbta-routes"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/backend/ingest-mbta-routes:v1.0.0"
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

resource "google_cloud_run_v2_job" "ingest_nws_weather" {
  name     = "ingest-nws-weather"
  location = var.location

  deletion_protection = false

  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      service_account = var.default_sa_compute_engine
      containers {
        name  = "ingest-nws-weather"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/backend/ingest-nws-weather:v1.0.0"
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

resource "google_cloud_run_v2_job" "transform" {
  name     = "transform"
  location = var.location

  deletion_protection = false

  template {
    task_count  = 1
    parallelism = 0
    template {
      service_account = google_service_account.dbt_bigquery.email
      containers {
        name  = "transform"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/backend/transform:v1.0.0"
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