# Credentials
variable "credentials" {
  description = "Path to GCP service account key file"
  default = "../keys/gcp-terraform-sa.json"
}

# Project Details
variable "project_id" {
  description = "Project ID"
  default = "mbta-reliability-analytics"
}

variable "location" {
  description = "Project Location"
  default = "us-east1"
}

# Default Service Accounts
variable "default_sa_compute_engine" {
  description = "Default compute service account"
  default = "558105773739-compute@developer.gserviceaccount.com"
}

variable "default_sa_google_apis" {
  description = "Google APIs Service Agent"
  default = "558105773739@cloudservices.gserviceaccount.com"
}

variable "default_sa_google_container_registry" {
  description = "Google Container Registry Service Agent"
  default = "service-558105773739@containerregistry.iam.gserviceaccount.com"
}

variable "default_sa_artifact_registry" {
  description = "Artifact Registry Service Agent"
  default = "service-558105773739@gcp-sa-artifactregistry.iam.gserviceaccount.com"
}

variable "default_sa_bigquery_data_transfer" {
  description = "BigQuery Data Transfer Service Agent"
  default = "service-558105773739@gcp-sa-bigquerydatatransfer.iam.gserviceaccount.com"
}

variable "default_sa_cloud_scheduler" {
  description = "Cloud Scheduler Service Account"
  default = "service-558105773739@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
}

variable "default_sa_dataform" {
  description = "Dataform Service Account"
  default = "service-558105773739@gcp-sa-dataform.iam.gserviceaccount.com"
}

variable "default_sa_cloud_pubsub" {
  description = "Cloud Pub/Sub Service Account"
  default = "service-558105773739@gcp-sa-pubsub.iam.gserviceaccount.com"
}

variable "default_sa_cloud_run" {
  description = "Google Cloud Run Service Agent"
  default = "service-558105773739@serverless-robot-prod.iam.gserviceaccount.com"
}