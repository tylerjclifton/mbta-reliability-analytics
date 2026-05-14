resource "google_cloud_run_v2_job" "ingestion_mbta_alerts" {
  name     = "ingestion-mbta-alerts"
  location = var.location

  deletion_protection = false

  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      service_account = var.default_sa_compute_engine
      containers {
        name  = "ingestion-mbta-alerts"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-mbta-alerts:v1.0.0"
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

resource "google_cloud_run_v2_job" "ingestion_mbta_routes" {
  name     = "ingestion-mbta-routes"
  location = var.location

  deletion_protection = false

  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      service_account = var.default_sa_compute_engine
      containers {
        name  = "ingestion-mbta-routes"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-mbta-routes:v1.0.0"
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

resource "google_cloud_run_v2_job" "ingestion_nws_weather" {
  name     = "ingestion-nws-weather"
  location = var.location

  deletion_protection = false

  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      service_account = var.default_sa_compute_engine
      containers {
        name  = "ingestion-nws-weather"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-nws-weather:v1.0.0"
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

resource "google_cloud_run_v2_job" "transform_pipeline" {
  name     = "transform-pipeline"
  location = var.location

  deletion_protection = false

  template {
    task_count  = 1
    parallelism = 0
    template {
      service_account = google_service_account.dbt_bigquery.email
      containers {
        name  = "transform-pipeline"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/transform-pipeline:v1.0.1"
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