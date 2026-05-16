# Use the official Python base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies needed for PostgreSQL (psycopg2) and general build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project code into the container
COPY . /app/

# --- FIX: COPY AND CONFIGURE ENTRYPOINT SCRIPT ---
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose the default port Django runs on
EXPOSE 8002

# --- FIX: DECLARE THE ENTRYPOINT RUNNER ---
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]

# Default command to run the application (Passed as parameters to entrypoint.sh)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8002"]