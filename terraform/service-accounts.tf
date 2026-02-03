# Terraform Runner Service Account
resource "google_service_account" "custom_sa_terraform_runner" {
  account_id   = "terraform-runner"
  display_name = "Terraform Runner"
}