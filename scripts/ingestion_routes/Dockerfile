# Use the official Python 3.11 slim image as the base image.
# This image is lightweight and includes only essential components.
FROM python:3.11-slim

# Set the working directory inside the container to /app.
# All following commands will be run relative to this directory.
WORKDIR /app

# Set an environment variable that Google libraries use to locate
# the credentials file for authenticating with Google Cloud.
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/keyfile.json"

# Copy the requirements.txt file from your local machine into the container.
# This file lists the Python dependencies needed to run your script.
COPY requirements.txt .

# Copy the service account key file used for Google Cloud authentication.
# This is the file referred to by the GOOGLE_APPLICATION_CREDENTIALS variable.
COPY keyfile.json /app/

# Install the Python dependencies listed in requirements.txt.
# The --no-cache-dir option prevents caching to keep the image size small.
RUN pip install --no-cache-dir -r requirements.txt

# Copy all other files from your local project directory into the container.
# This includes your ingestion script and any supporting files.
COPY . .

# Define the default command to run when the container starts.
# This tells Docker to run your Python ingestion script.
CMD ["python3", "ingestion_routes.py"]