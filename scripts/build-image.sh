#!/bin/bash
# Build and push a component's Docker image to Artifact Registry.
#
# Usage:  scripts/build-image.sh <ingest|transform|serve> <tag>
#
# Normally run by CI/CD (.github/workflows/ci.yml), which builds all three with
# the commit as the tag and deploys them with `terraform apply -var image_tag=…`.

set -euo pipefail

COMPONENT="${1:?usage: $0 <ingest|transform|serve> <version>}"
VERSION="${2:?usage: $0 <ingest|transform|serve> <version>}"

PROJECT_ID="mbta-reliability-analytics"
REGION="us-east1"

# The dashboard lives in the frontend repository; jobs in backend
case "${COMPONENT}" in
  ingest|transform) REPOSITORY="backend" ;;
  serve)            REPOSITORY="frontend" ;;
  *) echo "Unknown component: ${COMPONENT}" >&2; exit 1 ;;
esac

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${COMPONENT}:${VERSION}"

# Each component builds from its own folder (Dockerfile + requirements.txt)
cd "$(dirname "$0")/../${COMPONENT}"

echo "Building ${IMAGE}..."
docker build --platform linux/amd64 -t "${IMAGE}" .

echo "Pushing ${IMAGE}..."
docker push "${IMAGE}"

echo "✅ Pushed ${IMAGE}"
