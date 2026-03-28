#!/bin/bash
set -e

# =============================================================================
# Xprinter Server — Linux Deploy Script
# Ishlatish: bash deploy.sh
# =============================================================================

echo "=============================="
echo "  Xprinter Server Deploy"
echo "=============================="

# 1. System dependencies
echo "[1/7] System paketlar o'rnatilmoqda..."
sudo apt-get update -qq
sudo apt-get install -y -qq docker.io docker-compose-plugin git curl ufw nginx certbot python3-certbot-nginx

# Docker xizmatini yoqish
sudo systemctl enable docker
sudo systemctl start docker

# 2. Project clone
echo "[2/7] Repo klonlanmoqda..."
APP_DIR="/opt/xprinter"
if [ -d "$APP_DIR" ]; then
    cd "$APP_DIR" && sudo git pull origin main
else
    sudo git clone https://github.com/Ikhtiyor-s/xprinter.git "$APP_DIR"
    cd "$APP_DIR"
fi

# 3. .env yaratish
echo "[3/7] .env sozlanmoqda..."
if [ ! -f "$APP_DIR/.env" ]; then
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    WEBHOOK_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

    cat > "$APP_DIR/.env" << ENVEOF
SECRET_KEY=${SECRET_KEY}
DEBUG=false
ALLOWED_HOSTS=YOUR_DOMAIN_OR_IP
WEBHOOK_SECRET=${WEBHOOK_SECRET}
CORS_ORIGINS=https://YOUR_DOMAIN

DB_NAME=xprinter
DB_USER=xprinter
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=db
DB_PORT=5432

REDIS_URL=redis://redis:6379/0
PORT=9090
GUNICORN_WORKERS=3
SECURE_SSL_REDIRECT=false
ENVEOF

    echo ""
    echo "  ╔══════════════════════════════════════════════╗"
    echo "  ║  .env fayl yaratildi!                        ║"
    echo "  ║  ALLOWED_HOSTS va CORS_ORIGINS ni tuzating:  ║"
    echo "  ║  nano /opt/xprinter/.env                     ║"
    echo "  ╚══════════════════════════════════════════════╝"
    echo ""
    echo "  SECRET_KEY va DB_PASSWORD avtomatik yaratildi."
    echo "  .env ni to'g'irlab, qayta ishga tushiring: bash deploy.sh"
    echo ""

    # ALLOWED_HOSTS to'g'irlanmasa to'xtatish
    read -p "  ALLOWED_HOSTS tayyor bo'lsa ENTER bosing (yoki Ctrl+C): "
fi

# 4. Firewall
echo "[4/7] Firewall sozlanmoqda..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# 5. Docker build & start
echo "[5/7] Docker konteynerlar ishga tushirilmoqda..."
cd "$APP_DIR"
sudo docker compose down 2>/dev/null || true
sudo docker compose up -d --build

# Konteynerlar tayyor bo'lishini kutish
echo "  Konteynerlar yuklanmoqda..."
sleep 10

# 6. Health check
echo "[6/7] Health check..."
for i in 1 2 3 4 5; do
    if curl -sf http://localhost:9090/api/v2/health/ > /dev/null 2>&1; then
        echo "  Server ishlayapti!"
        break
    fi
    echo "  Kutilmoqda... ($i/5)"
    sleep 5
done

# 7. Nginx reverse proxy
echo "[7/7] Nginx sozlanmoqda..."
DOMAIN=$(grep ALLOWED_HOSTS "$APP_DIR/.env" | head -1 | cut -d= -f2 | cut -d, -f1)

sudo tee /etc/nginx/sites-available/xprinter > /dev/null << NGINXEOF
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:9090;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 30s;
        proxy_read_timeout 60s;
    }

    location /static/ {
        alias /opt/xprinter/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /opt/xprinter/media/;
        expires 7d;
    }
}
NGINXEOF

sudo ln -sf /etc/nginx/sites-available/xprinter /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "=============================="
echo "  Deploy tayyor!"
echo "=============================="
echo ""
echo "  Server:  http://${DOMAIN}"
echo "  Health:  http://${DOMAIN}/api/v2/health/"
echo "  Admin:   http://${DOMAIN}/admin/"
echo ""
echo "  SSL o'rnatish:"
echo "  sudo certbot --nginx -d ${DOMAIN}"
echo ""
echo "  Loglar:"
echo "  sudo docker compose -f /opt/xprinter/docker-compose.yml logs -f"
echo ""
