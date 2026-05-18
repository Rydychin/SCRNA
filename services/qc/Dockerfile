# Start from a small Python 3.12 image.
FROM python:3.12-slim

# Prevent Python from creating extra cache files.
# Tell Python to output logs immediately.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Use /app as the main working folder inside the container.
WORKDIR /app

# Create a safer non-root user and install certificates for HTTPS connections.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy the list of Python dependencies into the image.
COPY requirements.txt /app/requirements.txt

# Install the Python packages listed in requirements.txt.
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the QC script into the image.
COPY qc.py /app/qc.py

# Give appuser permission to access all the app files.
RUN chown -R appuser:appuser /app

# Run the container as the safer non-root user.
USER appuser
