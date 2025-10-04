# mbta-dashboard-backend

Docker Image Terminal Commands:

Build docker image: docker build --platform linux/amd64 -t us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-(alerts, stops, routes, shapes):v4 .

Push docker image to Artifact Registry: docker push us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-(alerts, stops, routes, shapes):v4

Cloud Run URL: https://us-east1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/mbta-reliability-analytics/jobs/ingestion-(alerts, stops, routes, shapes):run