#!/usr/bin/env bash
set -e

echo "Starting build process..."

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations (optional - uncomment if you want auto-migrations)
# python manage.py migrate --noinput

echo "Build completed successfully!"