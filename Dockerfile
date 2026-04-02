FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
RUN pip install --no-cache-dir \
    django==5.1 \
    djangorestframework==3.15.2 \
    django-cors-headers==4.4.0 \
    requests==2.32.3 \
    Pillow==11.2.1 \
    gunicorn==22.0.0

# Copy project
COPY . .

# SQLite DB volume uchun
RUN mkdir -p /data

# Entrypoint (root sifatida copy + chmod)
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app /data
USER appuser

# Migrate va start
EXPOSE 9000

CMD ["/docker-entrypoint.sh"]
