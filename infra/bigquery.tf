# Stage dataset - raw API dumps from Cloud Run jobs
resource "google_bigquery_dataset" "stage" {
  dataset_id    = "stage"
  friendly_name = "Stage Dataset"
  description   = "Raw data from API ingestion jobs (all sources)"
  location      = var.location
}

# MBTA dataset - data sourced from MBTA
resource "google_bigquery_dataset" "mbta" {
  dataset_id    = "mbta"
  friendly_name = "MBTA Dataset"
  description   = "Data sourced from MBTA"
  location      = var.location
}

# NWS dataset - data sourced from National Weather Service
resource "google_bigquery_dataset" "nws" {
  dataset_id    = "nws"
  friendly_name = "NWS Dataset"
  description   = "Data sourced from National Weather Service"
  location      = var.location
}

# Gold dataset - cross-domain analytics and final aggregations
resource "google_bigquery_dataset" "gold" {
  dataset_id    = "gold"
  friendly_name = "Gold Dataset"
  description   = "Final analytics tables combining all data sources"
  location      = var.location
}
