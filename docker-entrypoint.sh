#!/bin/bash
set -e

# Symlink bo'lsa o'chirish
if [ -L /app/db.sqlite3 ]; then
    rm /app/db.sqlite3
fi

# Migratsiyalarni qo'llash (mavjud DB ga zarar bermaydi)
echo "Migratsiyalar tekshirilmoqda..."
python manage.py migrate --settings=settings --run-syncdb 2>/dev/null || python manage.py migrate --settings=settings

echo "Server ishga tushmoqda: 0.0.0.0:9000"
exec python manage.py runserver 0.0.0.0:9000 --settings=settings
