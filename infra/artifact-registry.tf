# ══════════════════════════════════════════════════════════════════════════════
# Artifact Registry — images for the jobs (backend) and dashboard (frontend)
#
# Cleanup: keep the 2 most recent builds of each image and delete the rest
# once they're a day old. Git holds the code for every older build, and CI
# rebuilds from it, so the registry keeps only what Cloud Run may run: the
# newest build, and the one before it, which is still running when a deploy
# fails after the push. Each build is one version (scripts/build-image.sh).
# Measured 2026-11-15: keeping 30 days of builds held 52 GB, ~$5/month (the
# free tier is 0.5 GB).
# ══════════════════════════════════════════════════════════════════════════════

locals {
  image_repositories = {
    backend  = "MBTA backend Docker images (ingest, transform)"
    frontend = "MBTA frontend Docker images (serve)"
  }
}

resource "google_artifact_registry_repository" "repo" {
  for_each = local.image_repositories

  location      = var.location
  repository_id = each.key
  format        = "DOCKER"
  description   = each.value

  cleanup_policy_dry_run = false

  # Policies are evaluated together: KEEP wins over DELETE.
  cleanup_policies {
    id     = "keep-2-most-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 2
    }
  }
  cleanup_policies {
    id     = "delete-older-than-1-day"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "86400s" # 1 day
    }
  }
}
