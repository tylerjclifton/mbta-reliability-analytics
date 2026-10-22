# ══════════════════════════════════════════════════════════════════════════════
# Secret Manager
#
# Terraform owns the secret (its existence, replication, and who can read it —
# see iam.tf); the value is added by hand so it never appears in code or state:
#   printf '%s' "<key>" | gcloud secrets versions add mbta-api-key --data-file=-
# ══════════════════════════════════════════════════════════════════════════════

# MBTA V3 API key, read by the alerts and routes ingest jobs
resource "google_secret_manager_secret" "mbta_api_key" {
  secret_id = "mbta-api-key"

  replication {
    auto {}
  }

  lifecycle {
    prevent_destroy = true
  }
}
