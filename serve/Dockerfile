# Streamlit dashboard served by Cloud Run (infra/cloud-run-services.tf).
# Built from serve/ (scripts/build-image.sh serve <version>).
FROM python:3.13-slim

# Set the working directory inside the container
WORKDIR /app

# Install dependencies first so this layer is cached across code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app, its helpers, and the theme (tests stay out of the image)
COPY app.py helpers.py ./
COPY .streamlit/ .streamlit/

# Cloud Run sends traffic to 8080
EXPOSE 8080

CMD ["streamlit", "run", "app.py", \
     "--server.port=8080", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
