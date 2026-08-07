#!/usr/bin/env bash
set -e

echo "Starting build process..."

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations automatically so the database stays up to date
python manage.py migrate --noinput

echo "Build completed successfully!"