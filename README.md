# Xprinter — Printer Management System

Oshxona va restoran buyurtmalarini avtomatik chop etish tizimi.
Nonbor, Telegram, Yandex Food va boshqa platformalar bilan integratsiya.

---

## Imkoniyatlar

- Bir nechta printer boshqaruvi (Network, USB, Cloud, WiFi)
- Kategoriya va mahsulot bo'yicha printer mapping
- Har bir biznes uchun alohida chek shablonlari
- Nonbor API dan avtomatik buyurtma polling
- Tashqi servislar integratsiyasi (Yandex, Uzum, Express24, iiko)
- Cloud printing — masofadan chop etish (Print Agent orqali)
- Printer monitoring + Telegram bildirishnomalar
- Multi-tenant: har bir seller faqat o'z ma'lumotlarini ko'radi

---

## Arxitektura

```
Internet --> Nginx (80/443) --> xprinter (API server)
                                    |
                                    +--> PostgreSQL (ma'lumotlar)
                                    +--> Redis (cache)
                                    +--> Worker (polling + monitoring)
```

| Komponent | Texnologiya | Vazifasi |
|-----------|-------------|----------|
| API Server | Django + DRF + Gunicorn | REST API, webhook qabul |
| Worker | Django management command | Buyurtma polling, timeout monitoring |
| Database | PostgreSQL 16 | Ma'lumotlar saqlash |
| Cache | Redis 7 | Menyu cache, session |
| Reverse Proxy | Nginx | SSL, static files, load balancing |
| Desktop Agent | Python (PyQt5) | Masofadan chop etish |

---

## API

60 ta endpoint, 14 bo'lim. To'liq hujjat: [API.md](API.md)

| Bo'lim | Endpoint soni | Tavsif |
|--------|-------------|--------|
| Admin Auth | 2 | Login/Logout |
| Printer CRUD | 7 | Printer boshqaruvi |
| Category Mapping | 5 | Kategoriya-printer ulash |
| Product Mapping | 5 | Mahsulot-printer ulash |
| Print Jobs | 4 | Chop etish tarixi |
| Print Agent | 5 | Desktop agent uchun |
| Nonbor Config | 5 | API sozlamalari |
| Agent Credentials | 4 | Agent login/parol |
| Order Services | 4 | Tashqi integratsiyalar |
| Integration Templates | 4 | Shablon boshqaruvi |
| Receipt Templates | 4 | Chek shablonlari |
| Nonbor Polling | 5 | Buyurtma olish |
| Notifications | 6 | Telegram bildirishnomalar |
| Health Check | 1 | Server holati |

---

## Xavfsizlik

- Token, Basic, Agent, Webhook — 4 xil auth mexanizm
- Har bir seller faqat o'z business_id ma'lumotlarini ko'radi (IDOR himoya)
- Parollar Django hashers bilan hash qilingan (PBKDF2)
- API secret va tokenlar response da masked qaytadi
- CSRF, HSTS, XSS, Clickjacking himoyalari
- Rate limiting: 20/min anonymous, 120/min authenticated
- Webhook secret constant-time comparison (hmac)
- Cloud printer timeout: 20 sekund (sozlanadi)

---

## Chop etish flow

```
Buyurtma (Nonbor/Webhook/Qo'lda)
       |
  Kategoriya/Mahsulot mapping
       |
  Har bir printerga alohida chek
       |
  +-- Network printer --> TCP socket --> ESC/POS
  +-- USB printer --> win32print --> ESC/POS
  +-- Cloud printer --> PrintJob(pending) --> Agent poll --> Chop
       |
  Xatolik bo'lsa --> Telegram guruhga xabar
```

---

## Tech Stack

| Qatlam | Texnologiya |
|--------|-------------|
| Backend | Python 3.11, Django 5.1, DRF 3.15 |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Server | Gunicorn, Nginx |
| Container | Docker, Docker Compose |
| Desktop Agent | Python, PyQt5, ESC/POS |
| Monitoring | Telegram Bot API |

---

## Deploy

```bash
git clone https://github.com/Ikhtiyor-s/xprinter.git /opt/xprinter
cd /opt/xprinter
cp .env.example .env
nano .env  # SECRET_KEY, DB_PASSWORD, ALLOWED_HOSTS
docker compose up -d --build
```

Batafsil: [deploy.sh](deploy.sh)

---

## Litsenziya

Yopiq loyiha. Barcha huquqlar himoyalangan.
