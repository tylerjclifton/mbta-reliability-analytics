#!/bin/bash
# Deploy dbt transformation job to Cloud Run

set -e

PROJECT_ID="mbta-reliability-analytics"
REGION="us-east1"
IMAGE_NAME="mbta-transform"
REPOSITORY="data-ingestion"

echo "Building Docker image..."
cd "$(dirname "$0")"
docker build --platform linux/amd64 \
  -t "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest" \
  -f Dockerfile \
  ../..

echo "Pushing image to Artifact Registry..."
docker push "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"

echo "Updating Cloud Run job via Terraform..."
cd ../../terraform
terraform apply -auto-approve

echo "Deployment complete!"
echo "To trigger manually: gcloud run jobs execute mbta-transform --region=${REGION}"
