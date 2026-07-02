#!/bin/bash
# Deploy dbt transformation job to Cloud Run

set -e

PROJECT_ID="mbta-reliability-analytics"
REGION="us-east1"
IMAGE_NAME="transform"
REPOSITORY="backend"
VERSION="${1:-v1.0.0}"  # Accept version as argument, default to v1.0.0

echo "Building Docker image with version ${VERSION}..."
cd "$(dirname "$0")"
docker build --platform linux/amd64 \
  -t "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${VERSION}" \
  -f Dockerfile \
  ../..

echo "Pushing image to Artifact Registry..."
docker push "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${VERSION}"

echo ""
echo "✅ Docker image pushed successfully!"
echo "📝 Next steps:"
echo "   1. Update infra/cloud-run-jobs.tf to use :${VERSION}"
echo "   2. Run: cd infra && terraform apply"
echo "   3. Test: gcloud run jobs execute transform --region=${REGION}"
echo ""
