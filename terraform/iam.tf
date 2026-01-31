# Assign the Editor role to the Terraform Runner Service Account
resource "google_project_iam_member" "terraform_runner_sa" {
    project = var.project_id
    role   = "roles/editor"
    member = "serviceAccount:${google_service_account.terraform_runner_sa.email}"
}