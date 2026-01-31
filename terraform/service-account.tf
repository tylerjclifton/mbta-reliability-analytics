# Terraform Runner Service Account
resource "google_service_account" "terraform_runner_sa" {
  account_id   = "terraform-runner"
  display_name = "Terraform Runner"
}