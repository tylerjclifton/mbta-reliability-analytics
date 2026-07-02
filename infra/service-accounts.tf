# Terraform Runner Service Account
resource "google_service_account" "terraform_runner" {
  account_id   = "terraform-runner"
  display_name = "Terraform Runner"
}

# dbt Service Account
resource "google_service_account" "dbt_bigquery" {
  account_id   = "dbt-bigquery"
  display_name = "dbt BigQuery"
}

# Serve (Streamlit dashboard) Service Account
resource "google_service_account" "serve_bigquery" {
  account_id   = "serve-bigquery"
  display_name = "Serve BigQuery (read-only)"
}