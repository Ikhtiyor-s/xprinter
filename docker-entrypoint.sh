#!/bin/bash
set -e

# Faqat SECRET_KEY majburiy
if [ -z "$SECRET_KEY" ]; then
    echo "ERROR: SECRET_KEY .env da o'rnatilishi shart!"
    exit 1
fi

echo "Migratsiyalar..."
python manage.py migrate --settings=settings --run-syncdb 2>/dev/null || \
python manage.py migrate --settings=settings

python manage.py collectstatic --noinput --settings=settings 2>/dev/null || true

# Superuser (birinchi deploy uchun)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py createsuperuser --noinput 2>/dev/null || true
fi

if [ "$DEBUG" = "true" ] || [ "$DEBUG" = "True" ] || [ "$DEBUG" = "1" ]; then
    echo "DEV mode: python manage.py runserver 0.0.0.0:9000"
    exec python manage.py runserver 0.0.0.0:9000 --settings=settings
else
    echo "PROD mode: gunicorn 0.0.0.0:9000 (workers=${GUNICORN_WORKERS:-3})"
    exec gunicorn wsgi:application \
        --bind 0.0.0.0:9000 \
        --workers "${GUNICORN_WORKERS:-3}" \
        --timeout 60 \
        --keep-alive 5 \
        --access-logfile - \
        --error-logfile -
fi
