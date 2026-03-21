"""
Nonbor API bilan integratsiya.
Buyurtmalarni avtomatik olib, printerlarga yuboradi.
"""
import logging
import requests
from django.utils import timezone
from ..models import NonborConfig, PrintJob, OrderService

logger = logging.getLogger(__name__)


class NonborAPI:
    """Nonbor API client"""

    def __init__(self, config: NonborConfig):
        self.config = config
        self.base_url = config.api_url.rstrip('/')
        self.headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Telegram-Bot-Secret': config.api_secret,
        }

    def _get(self, path, params=None):
        url = f"{self.base_url}/{path}"
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"Nonbor API {resp.status_code}: {path}")
            return None
        except Exception as e:
            logger.error(f"Nonbor API xato: {path} - {e}")
            return None

    def get_orders(self):
        """Barcha buyurtmalarni olish (courier endpoint)"""
        data = self._get('telegram_bot/get-order-for-courier/')
        if not data or not data.get('success'):
            return []
        result = data.get('result', {})
        if isinstance(result, dict):
            return result.get('results', [])
        return result if isinstance(result, list) else []

    def get_seller_orders(self):
        """Seller ID bo'yicha buyurtmalarni olish"""
        if not self.config.seller_id:
            return self.get_orders()
        data = self._get(f'telegram_bot/sellers/{self.config.seller_id}/orders/')
        if not data or not data.get('success'):
            return []
        result = data.get('result', [])
        return result if isinstance(result, list) else []

    def get_order_detail(self, order_id):
        """Bitta buyurtma tafsilotini olish"""
        if self.config.seller_id:
            data = self._get(
                f'telegram_bot/sellers/{self.config.seller_id}/orders/{order_id}/'
            )
        else:
            data = self._get(f'order/{order_id}/detail/')
        if not data:
            return None
        return data.get('result', data)

    def get_business_info(self):
        """Biznes ma'lumotini olish"""
        data = self._get(f'business/{self.config.business_id}/detail/')
        if not data:
            return None
        return data.get('result', data)


def parse_nonbor_order(order_raw, business_id):
    """Nonbor API dan kelgan buyurtmani printer formatiga o'girish.

    Nonbor API response:
    {
        "id": 12345,
        "state": "ACCEPTED",
        "business": {"id": 96, "title": "Milliy"},
        "user": {"first_name": "Mirza", "last_name": "Aliev", "phone": "+998..."},
        "order_item": [{"product": {"id": 100, "name": "Palov"}, "count": 2, "price": 35000}],
        "total_price": 70000,
        "delivery_method": "DELIVERY",
        "payment_method": "CASH",
        "planned_datetime": "2026-03-03T18:00:00" | null,
        "created_at": "2026-03-03T14:30:00"
    }
    """
    business = order_raw.get('business', {}) or {}
    user = order_raw.get('user', {}) or {}

    # Items - Nonbor da "order_item" yoki "items"
    raw_items = order_raw.get('order_item', []) or order_raw.get('items', [])

    # Raw strukturani log qilamiz
    if raw_items:
        logger.info(f"Order #{order_raw.get('id')} item[0] keys: {list(raw_items[0].keys())}")
        logger.info(f"Order #{order_raw.get('id')} item[0] raw: {raw_items[0]}")

    items = []
    for it in raw_items:
        product = it.get('product', {}) or {}
        product_id = product.get('id') or it.get('product_id')
        name = product.get('name') or product.get('title') or it.get('name', 'Nomsiz')
        qty = it.get('count') or it.get('quantity', 1)
        price = it.get('price', 0) or product.get('price', 0)
        cat = product.get('menu_category', {}) or {}
        category_id = cat.get('id') or it.get('category_id')
        category_name = cat.get('name') or it.get('category_name', '')

        item_price = float(price) / 100

        # Qo'shimcha mahsulotlar (modifiers/additions)
        # Nonbor API da "additions", "modifiers", "extras", "add_ons" bo'lishi mumkin
        modifiers_raw = (
            it.get('additions') or
            it.get('modifiers') or
            it.get('extras') or
            it.get('add_ons') or
            it.get('addons') or
            []
        )
        modifiers = []
        for mod in modifiers_raw:
            mod_name = (
                mod.get('name') or
                (mod.get('product') or {}).get('name') or
                mod.get('title', '')
            )
            mod_qty = mod.get('count') or mod.get('quantity', 1)
            mod_price = mod.get('price', 0)
            mod_price_f = float(mod_price) / 100
            if mod_name:
                modifiers.append({
                    'name': mod_name,
                    'quantity': int(mod_qty),
                    'price': mod_price_f,
                })

        items.append({
            'product_id': product_id,
            'name': name,
            'quantity': int(qty),
            'price': item_price,
            'category_id': category_id,
            'category_name': category_name,
            'modifiers': modifiers,
        })

    # Scheduled time
    planned = order_raw.get('planned_datetime') or order_raw.get('planned_time', '')
    scheduled_time = ''
    if planned:
        try:
            from datetime import datetime
            if 'T' in str(planned):
                dt = datetime.fromisoformat(str(planned).replace('Z', '+00:00'))
                scheduled_time = dt.strftime('%d.%m.%Y %H:%M')
        except Exception:
            scheduled_time = str(planned)

    # Customer phone
    phone = (
        user.get('phone') or
        user.get('phone_number') or
        user.get('username') or
        order_raw.get('phone') or
        order_raw.get('customer_phone') or
        order_raw.get('contact_phone') or
        ''
    )

    # Delivery method
    delivery = order_raw.get('delivery_method', '') or ''

    # Customer address
    address = (
        order_raw.get('address') or
        order_raw.get('delivery_address') or
        order_raw.get('customer_address') or
        ''
    )
    if not address:
        for key in ('delivery_location', 'location', 'delivery_info'):
            loc = order_raw.get(key, {}) or {}
            if isinstance(loc, dict):
                address = loc.get('address') or loc.get('full_address') or loc.get('name') or ''
                if address:
                    break

    # Izoh (comment) - sotuvchiga yozilgan
    comment = (
        order_raw.get('comment') or
        order_raw.get('note') or
        order_raw.get('notes') or
        order_raw.get('seller_comment') or
        order_raw.get('order_comment') or
        order_raw.get('description') or
        ''
    )

    # Nonbor buyurtma raqami (order_number, number, display_number yoki id)
    order_num = (
        order_raw.get('order_number') or
        order_raw.get('number') or
        order_raw.get('display_number') or
        order_raw.get('id', '')
    )

    order_data = {
        'order_id': order_raw.get('id', 0),
        'order_number': str(order_num),
        'business_name': business.get('title') or business.get('name', ''),
        'customer_name': f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
        'customer_phone': phone,
        'customer_address': address,
        'delivery_method': delivery,
        'order_type': delivery,
        'payment_method': order_raw.get('payment_method', ''),
        'scheduled_time': scheduled_time,
        'comment': comment,
    }

    return order_data, items


def fetch_all_orders(api_url: str, api_secret: str) -> list:
    """Bitta API so'rov bilan barcha buyurtmalarni olish.
    Barcha bizneslarning buyurtmalari qaytadi — keyinchalik business_id bo'yicha filtrlash kerak.
    """
    url = f"{api_url.rstrip('/')}/telegram_bot/get-order-for-courier/"
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Telegram-Bot-Secret': api_secret,
        'User-Agent': 'NonborPrintAgent/1.0',
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            if not data or not data.get('success'):
                return []
            result = data.get('result', {})
            if isinstance(result, dict):
                return result.get('results', [])
            return result if isinstance(result, list) else []
        logger.warning(f"Markaziy polling [{resp.status_code}]: {url}")
        return []
    except Exception as e:
        logger.error(f"Markaziy polling xato: {url} - {e}")
        return []


def poll_and_print(config: NonborConfig, orders: list = None):
    """Nonbor API dan yangi buyurtmalarni olib, chop etish.

    Args:
        config: NonborConfig instansiyasi
        orders: Tayyor buyurtmalar ro'yxati (markaziy pollingdan).
                None bo'lsa — o'zi API ga so'rov yuboradi (manual poll uchun).

    Returns: (new_orders_count, printed_count, errors_count)
    """
    from .print_service import print_order

    if orders is None:
        # Manual poll — o'zi API ga so'rov yuboradi
        api = NonborAPI(config)
        orders = api.get_orders()

    if not orders:
        config.last_poll_at = timezone.now()
        config.save(update_fields=['last_poll_at'])
        return 0, 0, 0

    # Faqat shu biznesning ACCEPTED buyurtmalari — QATTIQ filtrlash
    biz_id = int(config.business_id)
    config_name = (config.business_name or '').strip().lower().rstrip('.').rstrip()
    accepted = []
    for o in orders:
        state = (o.get('state') or '').upper()
        if state != 'ACCEPTED':
            continue

        order_biz = o.get('business') or {}
        order_biz_id = order_biz.get('id')

        # business.id MAJBURIY — yo'q bo'lsa SKIP
        if order_biz_id is None:
            logger.warning(f"Buyurtma #{o.get('id')} SKIP: business.id yo'q!")
            continue

        try:
            if int(order_biz_id) != biz_id:
                continue
        except (ValueError, TypeError):
            continue

        accepted.append(o)

    # Allaqachon chop etilganlarni filter qilish (BARCHA bizneslardan)
    existing_order_ids = set(
        PrintJob.objects.filter(
            order_id__in=[o['id'] for o in accepted],
        ).values_list('order_id', flat=True).distinct()
    )

    new_orders = [o for o in accepted if o['id'] not in existing_order_ids]

    new_count = len(new_orders)
    printed = 0
    errors = 0

    for order_raw in new_orders:
        try:
            order_data, items = parse_nonbor_order(order_raw, biz_id)
            if not items:
                logger.warning(f"Buyurtma #{order_raw['id']} - items bo'sh")
                continue

            jobs = print_order(
                order_data=order_data,
                items=items,
                business_id=biz_id,
            )
            completed = sum(1 for j in jobs if j.status in ('completed', 'pending'))
            if completed:
                printed += 1
            logger.info(
                f"Nonbor #{order_raw['id']} -> {len(jobs)} printer, "
                f"{completed} muvaffaqiyatli"
            )
        except Exception as e:
            errors += 1
            logger.error(f"Buyurtma #{order_raw.get('id')} xato: {e}")

    config.last_poll_at = timezone.now()
    config.save(update_fields=['last_poll_at'])

    return new_count, printed, errors


# =============================================================================
# UNIVERSAL ORDER SERVICE POLLING
# Telegram bot, Yandex, Uzum, Express24, iiko va boshqa tizimlardan
# buyurtma olish uchun umumiy funksiya
# =============================================================================

def parse_generic_order(order_raw, business_id, service_type='custom'):
    """Har qanday tashqi tizimdan kelgan buyurtmani standart formatga keltirish.

    Kutilgan format (minimal):
    {
        "id": 123,                    # buyurtma ID
        "items": [                    # mahsulotlar
            {"name": "...", "quantity": 1, "price": 15000, "category_id": null, "product_id": null}
        ],
        "customer_name": "...",       # mijoz ismi (ixtiyoriy)
        "customer_phone": "...",      # telefon (ixtiyoriy)
        "delivery_type": "delivery",  # delivery/pickup/dine_in (ixtiyoriy)
        "comment": "",                # izoh (ixtiyoriy)
        "total_amount": 0,            # jami summa (ixtiyoriy)
        "address": "",                # manzil (ixtiyoriy)
        "payment_type": "",           # naqd/karta (ixtiyoriy)
    }
    """
    order_id = order_raw.get('id') or order_raw.get('order_id') or 0

    # Items parsing — turli formatlarni qo'llab-quvvatlash
    raw_items = order_raw.get('items') or order_raw.get('products') or order_raw.get('order_items') or []
    items = []
    for item in raw_items:
        items.append({
            'name': item.get('name') or item.get('product_name') or item.get('title') or 'Noma\'lum',
            'quantity': int(item.get('quantity') or item.get('count') or item.get('qty') or 1),
            'price': float(item.get('price') or item.get('amount') or item.get('unit_price') or 0),
            'category_id': item.get('category_id') or item.get('cat_id'),
            'product_id': item.get('product_id') or item.get('prod_id'),
            'modifiers': item.get('modifiers') or item.get('options') or [],
        })

    order_data = {
        'id': order_id,
        'order_number': str(order_raw.get('order_number') or order_raw.get('number') or order_id),
        'customer_name': order_raw.get('customer_name') or order_raw.get('client_name') or order_raw.get('name') or '',
        'customer_phone': order_raw.get('customer_phone') or order_raw.get('phone') or '',
        'delivery_type': order_raw.get('delivery_type') or order_raw.get('type') or 'delivery',
        'comment': order_raw.get('comment') or order_raw.get('note') or order_raw.get('notes') or '',
        'total_amount': float(order_raw.get('total_amount') or order_raw.get('total') or order_raw.get('amount') or 0),
        'address': order_raw.get('address') or order_raw.get('delivery_address') or '',
        'payment_type': order_raw.get('payment_type') or order_raw.get('payment_method') or '',
        'service_type': service_type,
        'business_id': business_id,
    }

    return order_data, items


def poll_and_print_service(service: OrderService):
    """OrderService orqali tashqi tizimdan buyurtmalarni olish va chop etish.

    Telegram bot, Yandex, Uzum va boshqa tizimlar uchun ishlaydi.
    API dan buyurtmalar ro'yxatini oladi, parse qiladi, printerlarga yuboradi.

    API javob formati (kutiladi):
    {
        "success": true,
        "orders": [
            {"id": 1, "items": [...], "customer_name": "...", ...}
        ]
    }
    yoki shunchaki list:
    [{"id": 1, "items": [...], ...}, ...]

    Returns: (new_orders_count, printed_count, errors_count)
    """
    from .print_service import print_order

    if not service.api_url:
        return 0, 0, 0

    # Service type aniqlash (template slug yoki service_name dan)
    service_type = 'custom'
    if service.template:
        service_type = service.template.slug or service.template.name.lower().replace(' ', '_')
    elif service.service_name:
        sn = service.service_name.lower()
        for known in ['nonbor', 'telegram', 'yandex', 'uzum', 'express24', 'iiko', 'rkeeper']:
            if known in sn:
                service_type = known
                break

    # API dan buyurtmalarni olish
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if service.api_secret:
        headers['Authorization'] = f'Bearer {service.api_secret}'
        headers['X-API-Key'] = service.api_secret
        headers['X-Telegram-Bot-Secret'] = service.api_secret
    if service.bot_token:
        headers['X-Bot-Token'] = service.bot_token

    try:
        resp = requests.get(
            service.api_url.rstrip('/'),
            headers=headers,
            params={'business_id': service.business_id, 'status': 'ACCEPTED'},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error(f"OrderService #{service.id} API xato: {resp.status_code}")
            return 0, 0, 0

        data = resp.json()
    except Exception as e:
        logger.error(f"OrderService #{service.id} so'rov xato: {e}")
        return 0, 0, 0

    # Response dan buyurtmalar ro'yxatini ajratish
    if isinstance(data, list):
        orders = data
    elif isinstance(data, dict):
        orders = (
            data.get('orders') or data.get('results') or
            data.get('result', {}).get('results') if isinstance(data.get('result'), dict) else None
        ) or data.get('data') or []
    else:
        orders = []

    if not orders:
        service.last_poll_at = timezone.now()
        service.save(update_fields=['last_poll_at'])
        return 0, 0, 0

    # Dublikat tekshiruvi — service_type + order_id bo'yicha
    order_ids = [o.get('id') or o.get('order_id') or 0 for o in orders]
    existing = set(
        PrintJob.objects.filter(
            service_type=service_type,
            order_id__in=order_ids,
            business_id=service.business_id,
        ).values_list('order_id', flat=True).distinct()
    )

    new_orders = [o for o in orders if (o.get('id') or o.get('order_id') or 0) not in existing]

    new_count = len(new_orders)
    printed = 0
    errors = 0

    for order_raw in new_orders:
        try:
            order_data, items = parse_generic_order(order_raw, service.business_id, service_type)
            if not items:
                logger.warning(f"OrderService #{service.id} buyurtma #{order_raw.get('id')} - items bo'sh")
                continue

            jobs = print_order(
                order_data=order_data,
                items=items,
                business_id=service.business_id,
            )
            # service_type ni har bir jobga yozish
            for j in jobs:
                if j.service_type == 'nonbor':  # default edi
                    j.service_type = service_type
                    j.external_order_id = str(order_raw.get('id') or order_raw.get('order_id') or '')
                    j.save(update_fields=['service_type', 'external_order_id'])

            completed = sum(1 for j in jobs if j.status in ('completed', 'pending'))
            if completed:
                printed += 1
            logger.info(
                f"[{service_type}] #{order_raw.get('id')} -> {len(jobs)} printer, "
                f"{completed} muvaffaqiyatli"
            )
        except Exception as e:
            errors += 1
            logger.error(f"[{service_type}] buyurtma #{order_raw.get('id')} xato: {e}")

    service.last_poll_at = timezone.now()
    service.save(update_fields=['last_poll_at'])

    return new_count, printed, errors
