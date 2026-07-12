FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (needed for compiling some python packages if any)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy the application source
COPY . .

# Install the application as a package
RUN pip install --default-timeout=100 --no-cache-dir .

# Remove unnecessary requirements.txt if present
RUN rm -f requirements.txt

# The command is defined in docker-compose.yml because we use this image for both API and Worker
