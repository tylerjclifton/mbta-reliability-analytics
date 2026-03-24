resource "google_cloud_run_v2_job" "ingestion_alerts" {
  name     = "ingestion-alerts"
  location = var.location
  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      containers {
        name  = "ingestion-alerts"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-alerts@sha256:c50e7cea84f2e6831ff6916f8fe7744e273d7497cf26404f3457ebf8b06b7f19"
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
  name     = "ingestion-routes"
  location = var.location
  template {
    task_count  = 1 # Total number of tasks to run
    parallelism = 0 # Maximum number of tasks to run concurrently
    template {
      containers {
        name  = "ingestion-routes"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-routes@sha256:d89fee1b441b1bc5b7d94788f3ff176db88f5f248bbec23e92ed65c5979a3d61"
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

resource "google_cloud_run_v2_job" "dbt_transform" {
  name     = "dbt-transform"
  location = var.location
  
  deletion_protection = false
  
  template {
    task_count  = 1
    parallelism = 0
    template {
      containers {
        name  = "dbt-transform"
        image = "us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/dbt-transform@sha256:520e9b5b6abcdbc0df7a1fed5d99c6ccfa363700805ed4a915dac80f06cc4930"
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
      timeout = "600s"  # 10 minutes for dbt to complete
    }
  }
}