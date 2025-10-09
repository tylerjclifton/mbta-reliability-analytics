# mbta-dashboard-backend

Docker Image Terminal Commands:

ALERTS
Build docker image: docker build --platform linux/amd64 -t us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-alerts:v6 .

Push docker image to Artifact Registry: docker push us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-(alerts, stops, routes, shapes):v6

Cloud Run URL: https://us-east1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/mbta-reliability-analytics/jobs/ingestion-alerts:run

ROUTES
Build docker image: docker build --platform linux/amd64 -t us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-routes:v4 .

Push docker image to Artifact Registry: docker push us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-routes:v4

Cloud Run URL: https://us-east1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/mbta-reliability-analytics/jobs/ingestion-routes:run

SHAPES
Build docker image: docker build --platform linux/amd64 -t us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-shapes:v4 .

Push docker image to Artifact Registry: docker push us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-shapes:v4

Cloud Run URL: https://us-east1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/mbta-reliability-analytics/jobs/ingestion-shapes:run

STOPS
Build docker image: docker build --platform linux/amd64 -t us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-stops:v4 .

Push docker image to Artifact Registry: docker push us-east1-docker.pkg.dev/mbta-reliability-analytics/data-ingestion/ingestion-stops:v4

Cloud Run URL: https://us-east1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/mbta-reliability-analytics/jobs/ingestion-stops:run