"""
Nonbor API bilan integratsiya.
Buyurtmalarni avtomatik olib, printerlarga yuboradi.
"""
import logging
import requests
from django.utils import timezone
from ..models import NonborConfig, PrintJob

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

        item_price = float(price) / 100 if price > 100000 else float(price)

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
            mod_price_f = float(mod_price) / 100 if mod_price > 100000 else float(mod_price)
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
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
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

    # Faqat shu biznesning ACCEPTED buyurtmalari
    biz_id = config.business_id
    accepted = []
    for o in orders:
        state = (o.get('state') or '').upper()
        order_biz_id = (o.get('business') or {}).get('id')
        # ACCEPTED holat + shu biznes (yoki biznes filter yo'q bo'lsa hammasi)
        is_accepted = state in ('ACCEPTED', 'NEW', 'CONFIRMED')
        is_our_biz = (order_biz_id == biz_id) or (order_biz_id is None)
        if is_accepted and is_our_biz:
            accepted.append(o)

    # Allaqachon chop etilganlarni filter qilish
    existing_order_ids = set(
        PrintJob.objects.filter(
            business_id=biz_id,
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
