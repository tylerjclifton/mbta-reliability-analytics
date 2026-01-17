variable "project_id" {
  description = "Project ID"
  default = "mbta-reliability-analytics"
}

variable "location" {
  description = "Project Location"
  default = "us-east1"
}

variable "bq_dataset_name" {
  description = "The name of the BigQuery dataset."
  default = "example_dataset"
}

variable "gcs_bucket_name" {
  description = "The name of the GCS bucket."
  default = "mbta-reliability-analytics-demo-bucket"
}

variable "gcs_storage_class" {
  description = "Bucket storage class."
  default = "STANDARD"
}