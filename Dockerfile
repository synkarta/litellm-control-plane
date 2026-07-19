# ==============================================================================
# NOTE: This Dockerfile is COMPLETELY OPTIONAL.
# You do not need Docker to run or develop this project.
#
# To run natively without Docker:
#   1. Create virtualenv:  python -m venv .venv
#   2. Install deps:      .venv/Scripts/pip install -r requirements.txt
#   3. Run API:           .venv/Scripts/python -m uvicorn src.api.main:app --reload
#
# Docker is only provided as an optional deployment option for containerized envs.
# ==============================================================================

# Use official lightweight Python 3.12 image
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /app

# Set environment variables:
# - PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files to disk
# - PYTHONUNBUFFERED: Prevents Python from buffering stdout and stderr for faster log output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DATABASE_URL="/app/data/control_plane.db"

# Install system dependencies if any are needed (e.g. SQLite CLI for debugging)
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create directory for persistent SQLite database
RUN mkdir -p /app/data

# Copy project source code
COPY src/ /app/src/

# Expose port (default 8000)
EXPOSE 8000

# Run FastAPI app with Uvicorn
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT}"]
