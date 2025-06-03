# Start from the official Python image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variable inside Dockerfile
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/keyfile.json"

# Copy the dependencies file and install
COPY requirements.txt .
COPY keyfile.json /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app files
COPY . .

# Run your script when the container starts
CMD ["python3", "ingestion_mbta_alerts.py"]
