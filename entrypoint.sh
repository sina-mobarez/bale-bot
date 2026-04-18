#!/bin/bash
set -e

echo "Waiting for database..."
until python -c "
import sys, psycopg2, os
try:
    psycopg2.connect(
        dbname=os.environ.get('DB_NAME','bale_bot_db'),
        user=os.environ.get('DB_USER','bale_bot_user'),
        password=os.environ.get('DB_PASSWORD','password'),
        host=os.environ.get('DB_HOST','db'),
        port=os.environ.get('DB_PORT','5432'),
    )
    sys.exit(0)
except Exception:
    sys.exit(1)
"; do
    echo "Database not ready, retrying in 2s..."
    sleep 2
done
echo "Database is ready ✓"

# Run migrations
echo "Running migrations..."
python manage.py migrate --no-input

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --no-input --clear

# Create superuser if not exists
echo "Creating superuser if needed..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(
        username=username,
        email=os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com'),
        password=os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin'),
    )
    print(f'Superuser {username} created.')
else:
    print(f'Superuser {username} already exists.')
"

# Start the requested service
case "$1" in
  web)
    echo "Starting Gunicorn web server..."
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers 3 \
      --worker-class sync \
      --timeout 120 \
      --access-logfile - \
      --error-logfile -
    ;;
  bot)
    echo "Starting Bale bot..."
    exec python manage.py runbot
    ;;
  *)
    exec "$@"
    ;;
esac
