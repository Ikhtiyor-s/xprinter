# Xprinter API Documentation

**Base URL:** `https://your-domain/api/v2/`

---

## Authentication

| Usul | Header | Kimlar uchun |
|------|--------|-------------|
| **Token** | `Authorization: Token <key>` | Admin panel |
| **Basic** | `Authorization: Basic base64(user:pass)` | Admin panel (axios) |
| **Agent** | `Authorization: Basic base64(user:pass)` | Print Agent desktop |
| **Webhook** | `X-Webhook-Secret: <secret>` | Nonbor backend |


---

## 1. Admin Auth

| Method | Endpoint | Auth | Tavsif |
|--------|----------|------|--------|
| POST | `/admin/login/` | Ochiq | Token olish |
| POST | `/admin/logout/` | Token/Basic | Token bekor qilish |

**POST /admin/login/** Request: ```json
{"username": "seller1", "password": "secret123"}
```
Response: ```json
{"success": true, "token": "abc123...", "business_id": 96, "business_name": "Milliy", "is_superadmin": false}
```

---

## 2. Printer CRUD

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| GET | `/printer/detect/` | Tizim printerlari |
| POST | `/printer/create/` | Yangi printer |
| GET | `/printer/list/?business_id=96` | Printerlar |
| GET | `/printer/{id}/detail/` | Batafsil |
| PUT | `/printer/{id}/update/` | Yangilash |
| DELETE | `/printer/{id}/delete/` | Ochirish |
| POST | `/printer/{id}/test-print/` | Test chop |

`connection_type`: network, usb, cloud, wifi

---

## 3. Printer Category Mapping

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| GET | `/printer-category/list/?business_id=96` | Royxat |
| GET | `/printer-category/by-printer/{printer_id}/` | Printer boyicha |
| POST | `/printer-category/assign/` | Ulash |
| POST | `/printer-category/bulk-assign/` | Koplab ulash |
| DELETE | `/printer-category/{id}/remove/` | Ochirish |

---

## 4. Printer Product Mapping

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| GET | `/printer-product/list/?business_id=96` | Royxat |
| GET | `/printer-product/by-printer/{printer_id}/` | Printer boyicha |
| POST | `/printer-product/assign/` | Ulash |
| POST | `/printer-product/bulk-assign/` | Koplab ulash |
| DELETE | `/printer-product/{id}/remove/` | Ochirish |

---

## 5. Print Jobs

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| GET | `/print-job/list/?business_id=96&status=failed` | Tarix |
| POST | `/print-job/{id}/retry/` | Qayta chop |
| POST | `/print-job/print-order/{order_id}/` | Qolda chop |
| POST | `/print-job/webhook/` | Nonbor callback (Webhook auth) |

`status`: pending, printing, completed, failed

---

## 6. Print Agent (Desktop App)

| Method | Endpoint | Auth | Tavsif |
|--------|----------|------|--------|
| POST | `/agent/auth/` | Ochiq (5/min) | Login |
| GET | `/print-job/agent/poll/?business_id=96` | Agent | Pending joblar |
| POST | `/print-job/agent/complete/` | Agent | Job tugadi |
| GET | `/agent/menu/{business_id}/` | Agent | Menyu |
| POST | `/agent/printer-sync/` | Agent | Printer sync |

---

## 7. Nonbor Config

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| GET | `/nonbor-config/list/` | Royxat |
| POST | `/nonbor-config/create/` | Yaratish |
| GET | `/nonbor-config/{business_id}/detail/` | Batafsil |
| PUT | `/nonbor-config/{business_id}/update/` | Yangilash |
| DELETE | `/nonbor-config/{business_id}/delete/` | Ochirish |

> `api_secret` response da masked. Update da masked yuborsangiz eski qiymat saqlanadi.

---

## 8. Agent Credentials

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| GET | `/agent-credential/list/?business_id=96` | Royxat |
| POST | `/agent-credential/create/` | Yaratish |
| PUT | `/agent-credential/{id}/update/` | Yangilash |
| DELETE | `/agent-credential/{id}/delete/` | Ochirish |

> `password` response da `********`. Update da `********` yuborsangiz parol ozgarmaydi.

---

## 9. Order Services

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| GET | `/order-service/list/?business_id=96` | Royxat |
| POST | `/order-service/create/` | Yaratish |
| PUT | `/order-service/{id}/update/` | Yangilash |
| DELETE | `/order-service/{id}/delete/` | Ochirish |

---

## 10. Integration Templates

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| GET | `/integration-template/list/?active_only=true` | Royxat |
| POST | `/integration-template/create/` | multipart/form-data |
| PUT | `/integration-template/{id}/update/` | multipart/form-data |
| DELETE | `/integration-template/{id}/delete/` | Ochirish |

---

## 11. Receipt Templates

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| GET | `/receipt-template/list/?business_id=96` | Royxat |
| GET | `/receipt-template/{business_id}/detail/` | Batafsil |
| POST | `/receipt-template/save/` | Yaratish/Yangilash |
| DELETE | `/receipt-template/{business_id}/delete/?template_type=delivery` | Ochirish |

`template_type`: delivery, pickup, dine_in, sched_del, sched_pick, admin

---

## 12. Nonbor Polling

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| POST | `/nonbor/poll/{business_id}/` | Bitta biznes poll |
| GET | `/nonbor/orders/{business_id}/` | Hozirgi buyurtmalar |
| POST | `/nonbor/poll-start/{business_id}/` | Polling yoqish |
| POST | `/nonbor/poll-stop/{business_id}/` | Polling ochirish |
| POST | `/nonbor/poll-all/` | Barcha bizneslar |

---

## 13. Notifications

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| GET | `/notification/list/?business_id=96&is_read=false` | Royxat |
| GET | `/notification/unread-count/?business_id=96` | Oqilmagan soni |
| POST | `/notification/mark-read/` | Oqilgan deb belgilash |
| POST | `/notification-config/save/` | Telegram sozlash |
| GET | `/notification-config/{business_id}/detail/` | Sozlama |
| POST | `/notification-config/test-telegram/` | Test xabar |

---

## 14. Health Check

| Method | Endpoint | Auth |
|--------|----------|------|
| GET | `/health/` | Ochiq |

Response: `{"status": "healthy", "database": "ok"}`

---

## Error Responses

```json
{"success": false, "error": "Xatolik tavsifi"}
```

| Kod | Manosi |
|-----|--------|
| 200 | Muvaffaqiyatli |
| 201 | Yaratildi |
| 400 | Notogri sorov |
| 401 | Autentifikatsiya kerak |
| 403 | Ruxsat berilmagan |
| 404 | Topilmadi |
| 429 | Rate limit |
| 503 | Server muammosi |

---

## Business ID Isolation

- **Superadmin**: barcha bizneslar
- **Oddiy seller**: faqat oz business_id si
- **Agent**: faqat AgentCredential.business_id
- Boshqa biznesga sorov = **403 Forbidden**

