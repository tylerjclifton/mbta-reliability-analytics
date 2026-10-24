# ══════════════════════════════════════════════════════════════════════════════
# Variables — project, deployment, schedules, alerting, and Google service agents
#
# Everything has a default except image_tag, which CI/CD sets on every deploy.
# ══════════════════════════════════════════════════════════════════════════════

# ── Project ───────────────────────────────────────────────────────────────────

variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "mbta-reliability-analytics"
}

variable "location" {
  description = "Region for every regional resource"
  type        = string
  default     = "us-east1"
}

# ── Deployment ────────────────────────────────────────────────────────────────

variable "image_tag" {
  description = <<-EOT
    Tag of the ingest, transform, and serve images to deploy. CI/CD sets it to
    the commit being deployed (.github/workflows/ci.yml). No default on purpose:
    a local plan must name the deployed tag, e.g.
      terraform plan -var image_tag=$(git rev-parse --short=12 origin/main)
  EOT
  type        = string
}

variable "github_repository" {
  description = "GitHub repository (owner/name) allowed to deploy via Workload Identity Federation"
  type        = string
  default     = "tylerjclifton/mbta-reliability-analytics"
}

# ── Schedules ─────────────────────────────────────────────────────────────────

variable "scheduler_time_zone" {
  description = "Cloud Scheduler time zone for cron jobs"
  type        = string
  default     = "America/New_York"
}

variable "alerts_ingestion_schedule" {
  description = "Cron for MBTA alerts ingestion. Every 15 minutes; each run snapshots the live feed, and the gap between runs bounds how precisely an alert's end is known."
  type        = string
  default     = "*/15 * * * *"
}

variable "weather_ingestion_schedule" {
  description = "Cron for NOAA weather ingestion. Daily at 6AM ET; NOAA publishes with a ~2-3 day lag."
  type        = string
  default     = "0 6 * * *"
}

variable "ridership_ingestion_schedule" {
  description = "Cron for MBTA ridership ingestion. Weekly (Mondays 6AM ET): the MBTA publishes in irregular batches weeks to months late, so new data is picked up within a week of whenever it lands."
  type        = string
  default     = "0 6 * * 1"
}

variable "stops_ingestion_schedule" {
  description = "Cron for MBTA stops ingestion. Weekly (Mondays 6:30AM ET); stations rarely change, and a new or renamed platform is picked up within a week."
  type        = string
  default     = "30 6 * * 1"
}

variable "routes_ingestion_schedule" {
  description = "Cron for MBTA routes ingestion. Yearly on Jan 1; routes rarely change."
  type        = string
  default     = "0 0 1 1 *"
}

variable "transform_schedule" {
  description = "Cron for the dbt transform job. Hourly at :35, just after the :30 alerts snapshot."
  type        = string
  default     = "35 * * * *"
}

# ── Dashboard ─────────────────────────────────────────────────────────────────

variable "serve_domain" {
  description = "Canonical domain for the Streamlit dashboard"
  type        = string
  default     = "tylerclifton.com"
}

# ── Alerting ──────────────────────────────────────────────────────────────────

variable "alert_email" {
  description = "Address that receives pipeline failure alerts (monitoring.tf)"
  type        = string
  default     = "tylerjclifton@outlook.com"
}

# ── Google service agents ─────────────────────────────────────────────────────
# Project-number-specific; granted by Google, documented in iam.tf

variable "default_sa_google_apis" {
  description = "Google APIs Service Agent"
  type        = string
  default     = "558105773739@cloudservices.gserviceaccount.com"
}

variable "default_sa_artifact_registry" {
  description = "Artifact Registry Service Agent"
  type        = string
  default     = "service-558105773739@gcp-sa-artifactregistry.iam.gserviceaccount.com"
}

variable "default_sa_cloud_scheduler" {
  description = "Cloud Scheduler Service Agent"
  type        = string
  default     = "service-558105773739@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
}

variable "default_sa_cloud_run" {
  description = "Cloud Run Service Agent"
  type        = string
  default     = "service-558105773739@serverless-robot-prod.iam.gserviceaccount.com"
}
