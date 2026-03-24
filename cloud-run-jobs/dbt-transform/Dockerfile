# Use Python 3.9 to match your local dbt environment
FROM python:3.9-slim

# Install git (required for some dbt packages) and other essentials
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire dbt project
COPY mbta_analytics_dbt/ /app/mbta_analytics_dbt/

# Copy GCP service account key
COPY keys/gcp-terraform-sa.json /app/keys/gcp-terraform-sa.json

# Set working directory to dbt project
WORKDIR /app/mbta_analytics_dbt

# Run dbt
CMD ["dbt", "run", "--profiles-dir", "."]
