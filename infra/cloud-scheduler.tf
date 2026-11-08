# ══════════════════════════════════════════════════════════════════════════════
# Cloud Scheduler — cron triggers for the Cloud Run jobs
#
# Each trigger POSTs to the Cloud Run Admin API's jobs.run endpoint as the
# job-scheduler service account, which may run only these jobs (iam.tf).
# Ingest schedules come from local.ingest_jobs (cloud-run-jobs.tf).
# ══════════════════════════════════════════════════════════════════════════════

locals {
  run_jobs_api = "https://${var.location}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.location}/jobs"
}

# ── Ingest triggers ───────────────────────────────────────────────────────────

resource "google_cloud_scheduler_job" "ingest" {
  for_each = { for name, job in local.ingest_jobs : name => job if job.schedule != null }

  name             = "ingest-${each.key}"
  schedule         = each.value.schedule
  time_zone        = var.scheduler_time_zone
  attempt_deadline = "180s"
  paused           = false

  # Retries the call that starts the job, if it fails: a job that never started
  # can't retry itself (max_retries in cloud-run-jobs.tf only covers failed runs)
  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "${local.run_jobs_api}/${google_cloud_run_v2_job.ingest[each.key].name}:run"
    oauth_token {
      service_account_email = google_service_account.job_scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

# ── Transform triggers ────────────────────────────────────────────────────────
# Hourly runs skip the slow-changing models tagged daily (transform/
# dbt_project.yml), and one full run a day builds everything, as does any run
# started another way: CI's post-deploy run or a manual one (decision 0017).

locals {
  transform_triggers = {
    "transform"      = { schedule = var.transform_schedule, exclude = "tag:daily" }
    "transform-full" = { schedule = var.transform_full_schedule, exclude = null }
  }
}

resource "google_cloud_scheduler_job" "transform" {
  for_each = local.transform_triggers

  name             = each.key
  schedule         = each.value.schedule
  time_zone        = var.scheduler_time_zone
  attempt_deadline = "600s" # 10 minutes
  paused           = false

  # Retries the call that starts the job, if it fails; the job itself never
  # retries (transform_max_retries in cloud-run-jobs.tf)
  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "${local.run_jobs_api}/${google_cloud_run_v2_job.transform.name}:run"
    # DBT_EXCLUDE is passed to `dbt build --exclude` (transform/run.py), for
    # this run only
    headers = each.value.exclude == null ? {} : { "Content-Type" = "application/json" }
    body = each.value.exclude == null ? null : base64encode(jsonencode({
      overrides = { containerOverrides = [{ env = [{ name = "DBT_EXCLUDE", value = each.value.exclude }] }] }
    }))
    oauth_token {
      service_account_email = google_service_account.job_scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

# The hourly trigger predates the full one; keep it rather than recreate it
moved {
  from = google_cloud_scheduler_job.transform
  to   = google_cloud_scheduler_job.transform["transform"]
}
