# Use Python 3.9 to match your local dbt environment
FROM python:3.9-slim

# Install git (required for some dbt packages) and other essentials
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory to the repository root
WORKDIR /app

# Copy only necessary files from the repository root
COPY requirements.txt /app/requirements.txt
COPY transformation/ /app/transformation/
COPY keys/gcp-dbt-sa.json /app/keys/gcp-dbt-sa.json

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Set working directory to transformation project
WORKDIR /app/transformation

# Run dbt
CMD ["dbt", "run", "--profiles-dir", "."]
