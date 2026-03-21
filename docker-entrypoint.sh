#!/bin/bash
set -e

# Symlink bo'lsa o'chirish
if [ -L /app/db.sqlite3 ]; then
    rm /app/db.sqlite3
fi

# Migratsiyalarni qo'llash (mavjud DB ga zarar bermaydi)
echo "Migratsiyalar tekshirilmoqda..."
python manage.py migrate --settings=settings --run-syncdb 2>/dev/null || python manage.py migrate --settings=settings

python manage.py collectstatic --noinput 2>/dev/null || true

if [ "$DEBUG" = "true" ] || [ "$DEBUG" = "True" ] || [ "$DEBUG" = "1" ]; then
    echo "DEV server ishga tushmoqda: 0.0.0.0:9000"
    exec python manage.py runserver 0.0.0.0:9000 --settings=settings
else
    echo "PROD server ishga tushmoqda: gunicorn 0.0.0.0:9000"
    exec gunicorn wsgi:application --bind 0.0.0.0:9000 --workers 3 --timeout 120 --access-logfile - --error-logfile -
fi
