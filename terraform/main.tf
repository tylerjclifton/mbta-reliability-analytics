terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.16.0"
    }
  }
}

provider "google" {
  credentials = file("../keys/mbta-reliability-analytics-sa.json")
  project     = "mbta-reliability-analytics"
  region      = "us-east1"
}