#!/bin/sh
set -e

# Wait for DB
if [ -n "$POSTGRES_HOST" ]; then
  echo "Waiting for PostgreSQL at $POSTGRES_HOST:$POSTGRES_PORT..."
  while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
    sleep 1
  done
fi

# Migrate DB
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Start Daphne (ASGI, for Channels) or Gunicorn (WSGI)
if [ "$USE_DAPHNE" = "1" ]; then
  exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
else
  exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
fi 