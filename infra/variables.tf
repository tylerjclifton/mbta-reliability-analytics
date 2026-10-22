# Project Details
variable "project_id" {
  description = "Project ID"
  default     = "mbta-reliability-analytics"
}

variable "location" {
  description = "Project Location"
  default     = "us-east1"
}

# Scheduler configuration
variable "scheduler_time_zone" {
  description = "Cloud Scheduler time zone for cron jobs"
  default     = "America/New_York"
}

variable "alerts_ingestion_schedule" {
  description = "Cron for MBTA alerts ingestion. Every 15 minutes; each run snapshots the live feed, and the gap between runs bounds how precisely an alert's end is known."
  default     = "*/15 * * * *"
}

variable "weather_ingestion_schedule" {
  description = "Cron for NOAA weather ingestion. Daily at 6AM ET; NOAA publishes with a ~2-3 day lag."
  default     = "0 6 * * *"
}

variable "ridership_ingestion_schedule" {
  description = "Cron for MBTA ridership ingestion. Weekly (Mondays 6AM ET) so newly published months are picked up within a week."
  default     = "0 6 * * 1"
}

variable "routes_ingestion_schedule" {
  description = "Cron for MBTA routes ingestion. Yearly on Jan 1; routes rarely change."
  default     = "0 0 1 1 *"
}

variable "transform_schedule" {
  description = "Cron for the dbt transform job. Hourly at :35, just after the :30 alerts snapshot."
  default     = "35 * * * *"
}

# Serve (dashboard) configuration
variable "serve_domain" {
  description = "Canonical domain for the Streamlit dashboard"
  default     = "tylerclifton.com"
}

# Google service agents (project-number-specific; granted by Google, documented in iam.tf)

variable "default_sa_google_apis" {
  description = "Google APIs Service Agent"
  default     = "558105773739@cloudservices.gserviceaccount.com"
}


variable "default_sa_artifact_registry" {
  description = "Artifact Registry Service Agent"
  default     = "service-558105773739@gcp-sa-artifactregistry.iam.gserviceaccount.com"
}


variable "default_sa_cloud_scheduler" {
  description = "Cloud Scheduler Service Account"
  default     = "service-558105773739@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
}



variable "default_sa_cloud_run" {
  description = "Google Cloud Run Service Agent"
  default     = "service-558105773739@serverless-robot-prod.iam.gserviceaccount.com"
}