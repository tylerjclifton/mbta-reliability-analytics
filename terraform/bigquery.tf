# Staging dataset - raw API dumps from Cloud Run jobs
resource "google_bigquery_dataset" "staging" {
  dataset_id    = "staging"
  friendly_name = "Staging Dataset"
  description   = "Raw data from API ingestion jobs (all sources)"
  location      = var.location
  
  # Optional: Set table expiration to 7 days to save costs
  default_table_expiration_ms = 604800000 # 7 days in milliseconds
}

# MBTA dataset - cleaned and transformed MBTA transit data
resource "google_bigquery_dataset" "mbta" {
  dataset_id    = "mbta"
  friendly_name = "MBTA Dataset"
  description   = "Cleaned and transformed MBTA transit data"
  location      = var.location
}

# Weather dataset - cleaned and transformed weather data (future)
resource "google_bigquery_dataset" "weather" {
  dataset_id    = "weather"
  friendly_name = "Weather Dataset"
  description   = "Cleaned and transformed weather data"
  location      = var.location
}

# Gold dataset - cross-domain analytics and final aggregations
resource "google_bigquery_dataset" "gold" {
  dataset_id    = "gold"
  friendly_name = "Gold Dataset"
  description   = "Final analytics tables combining all data sources"
  location      = var.location
}
