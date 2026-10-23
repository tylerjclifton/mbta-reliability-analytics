# ══════════════════════════════════════════════════════════════════════════════
# Quotas — the project's daily BigQuery query quota, pinned at Google's default
#
# Don't lower this as a cost cap. On 2026-10-23 a 50 GiB/day cap, and then a
# 200 GiB/day one, refused transform queries as "quotaExceeded" while the day's
# usage was ~11-12 GiB (Cloud Monitoring agreed), failing every hourly run.
# The custom quota misfires whatever its value, so it can't be trusted to stop
# only a runaway.
#
# Query cost is bounded per query instead: maximum_bytes_billed in
# transform/profiles.yml (dbt) and serve/app.py (dashboard). The $5/month
# budget (README, Cost) emails on anything that slips past those.
#
# This resource stays because a quota preference can't be deleted once
# created; keeping it in Terraform at the default keeps code and GCP matching.
# ══════════════════════════════════════════════════════════════════════════════

resource "google_cloud_quotas_quota_preference" "bigquery_query_usage_per_day" {
  parent   = "projects/${var.project_id}"
  name     = "bigquery-query-usage-per-day"
  service  = "bigquery.googleapis.com"
  quota_id = "QueryUsagePerDay"

  quota_config {
    preferred_value = 200 * 1024 * 1024 # MiB per day (the quota's unit) = 200 TiB, Google's default
  }

  justification = "Restore the default; a custom daily cap refused queries far below its limit."

  depends_on = [google_project_service.api["cloud_quotas"]]
}
