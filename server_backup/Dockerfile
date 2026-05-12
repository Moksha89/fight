# Use official Python runtime as base image
FROM python:3.11-slim-bullseye

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# Set work directory
WORKDIR /server

# Install system dependencies required for building Python packages and MySQL client
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    default-libmysqlclient-dev \
    pkg-config \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Ensure production helper script is executable
RUN chmod +x ./.helpers/production/wait_for_mysql.sh 2>/dev/null || true

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash kokoroko && \
    chown -R kokoroko:kokoroko /server

# Switch to non-root user
USER kokoroko

# Expose port (Daphne runs on 8000 by default)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python manage.py check --database default || exit 1

# Command to run the application
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "kokoroko.asgi:application"]
