#!/bin/bash
set -e

# Security checks
if [ "$DEBUG" != "true" ] && [ "$DEBUG" != "True" ] && [ "$DEBUG" != "1" ]; then
    if [ -z "$SECRET_KEY" ]; then
        echo "ERROR: SECRET_KEY is not set. Exiting."
        exit 1
    fi
    if [ -z "$ALLOWED_HOSTS" ] || [ "$ALLOWED_HOSTS" = "*" ]; then
        echo "ERROR: ALLOWED_HOSTS must be set (not *). Exiting."
        exit 1
    fi
    if [ -z "$WEBHOOK_SECRET" ]; then
        echo "ERROR: WEBHOOK_SECRET is not set. Exiting."
        exit 1
    fi
fi

echo "Migratsiyalar tekshirilmoqda..."
python manage.py migrate --settings=settings --run-syncdb 2>/dev/null || python manage.py migrate --settings=settings
python manage.py collectstatic --noinput 2>/dev/null || true

if [ "$DEBUG" = "true" ] || [ "$DEBUG" = "True" ] || [ "$DEBUG" = "1" ]; then
    echo "DEV server: 0.0.0.0:9000"
    exec python manage.py runserver 0.0.0.0:9000 --settings=settings
else
    echo "PROD server: gunicorn 0.0.0.0:9000"
    exec gunicorn wsgi:application         --bind 0.0.0.0:9000         --workers "${GUNICORN_WORKERS:-3}"         --timeout 30         --graceful-timeout 10         --keep-alive 5         --max-requests 1000         --max-requests-jitter 50         --access-logfile -         --error-logfile -
fi
