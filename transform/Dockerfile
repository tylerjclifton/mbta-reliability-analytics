# dbt transform job: builds silver views and gold tables, runs their tests,
# then checks bronze freshness. Built from transform/ (scripts/build-image.sh).
FROM python:3.13-slim

# Set the working directory inside the container
WORKDIR /app

# Install dependencies first so this layer is cached across model changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the dbt project (models, macros, tests, profiles)
COPY . .

# 1. `dbt build` — models + tests in DAG order; a failing test skips everything
#    downstream of it, so bad data never reaches gold
# 2. `dbt source freshness` — fails the run if an ingest job has stopped
#    writing to bronze (thresholds in models/bronze/_bronze__sources.yml)
# Uses the gcp target (attached service account, no keyfile).
CMD ["sh", "-c", "dbt build --profiles-dir . --target gcp && dbt source freshness --profiles-dir . --target gcp"]
