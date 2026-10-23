# ══════════════════════════════════════════════════════════════════════════════
# Quotas — hard caps that bound what a runaway can cost
#
# Google Cloud has no spending cap; the only "cap" is a script that removes the
# project's billing, which would stop the ingest jobs and permanently lose live
# MBTA alerts. These caps instead limit the parts that could run away, without
# touching ingest. The $5/month budget (README, Cost) emails long before either
# is reached.
#
#   BigQuery queries  200 GiB/day for the project (default: 200 TiB/day).
#                     Normal use is ~13 GiB/day; the busiest day on record was
#                     23 GiB (heavy development, 2026-10-22). Pinned at the cap
#                     all month it costs ~$31 past the free 1 TiB. Hitting it
#                     pauses the transform and the dashboard until the quota
#                     resets at midnight Pacific; the failed transform sends
#                     the usual failure email. Ingest keeps running: bronze
#                     loads are load jobs, not queries, so no data is lost.
#                     Applies to every query in the project, local dbt builds
#                     and console queries included.
#
#                     Enforcement trips well below the set value: at 50 GiB,
#                     individual queries were refused as "quotaExceeded" once
#                     the day's billed usage reached ~11 GiB (2026-10-23),
#                     while others in the same run passed; raising the cap to
#                     200 GiB cleared it (after ~20 minutes to propagate). The
#                     cause isn't documented, so keep the cap many times the
#                     busiest day, not just above it.
#   Dashboard         max 2 instances (cloud-run-services.tf).
# ══════════════════════════════════════════════════════════════════════════════

resource "google_cloud_quotas_quota_preference" "bigquery_query_usage_per_day" {
  parent   = "projects/${var.project_id}"
  name     = "bigquery-query-usage-per-day"
  service  = "bigquery.googleapis.com"
  quota_id = "QueryUsagePerDay"

  quota_config {
    preferred_value = 200 * 1024 # MiB per day (the quota's unit) = 200 GiB
  }

  # Cloud Quotas refuses decreases over 10% without this; the large drop from
  # the 200 TiB default is the point
  ignore_safety_checks = "QUOTA_DECREASE_PERCENTAGE_TOO_HIGH"
  justification        = "Cost cap: bounds a runaway query loop to about $31/month past the free tier."

  depends_on = [google_project_service.api["cloud_quotas"]]
}
