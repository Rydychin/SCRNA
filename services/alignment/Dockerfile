# Start from a small Python image so this service stays lightweight.
FROM python:3.12-slim

# Keep Python from writing cache files and make logs show up right away.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Everything for this service lives in /app inside the container.
WORKDIR /app

# Create a non-root user and install certificates for HTTPS connections.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency list first so Docker can cache package installs.
COPY requirements.txt /app/requirements.txt

# Install the Python dependencies for this service.
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy in the alignment script after dependencies are installed.
COPY align.py /app/align.py

# Let the non-root user read and run the files in /app.
RUN chown -R appuser:appuser /app

# Run as the non-root user by default.
USER appuser
