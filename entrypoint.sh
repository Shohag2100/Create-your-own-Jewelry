#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

echo "Waiting for database..."
# Optional: add a sleep if your DB container takes a moment to initialize
sleep 3 

echo "Applying database migrations..."
python manage.py migrate

echo "Creating superuser if it doesn't exist..."
# This creates a superuser automatically using environment variables without prompting
if [ "$DJANGO_SUPERUSER_USERNAME" ]; then
    python manage.py createsuperuser --noinput || echo "Superuser already exists."
fi

echo "Starting server..."
exec "$@"