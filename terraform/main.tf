terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.16.0"
    }
  }
}

provider "google" {
  credentials = file("../keys/gcp-terraform-sa.json")
  project     = "mbta-reliability-analytics"
  region      = "us-east1"
}

resource "google_storage_bucket" "terra-bucket" {
  name          = "mbta-reliability-analytics-demo-bucket"
  location      = "us-east1"
  force_destroy = true

  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "AbortIncompleteMultipartUpload"
    }
  }
}

resource "google_bigquery_dataset" "example_dataset" {
  dataset_id = "example_dataset"
  location   = "us-east1"
}