import os
import sys
import socket
import logging
import requests as _requests
from datetime import datetime
from collections import defaultdict

from django.utils import timezone

from ..models import Printer, PrinterCategory, PrinterProduct, PrintJob, ReceiptTemplate

logger = logging.getLogger(__name__)

# Windows printer support
IS_WINDOWS = sys.platform == 'win32'
if IS_WINDOWS:
    try:
        import win32print
        HAS_WIN32PRINT = True
    except ImportError:
        HAS_WIN32PRINT = False
        logger.warning("win32print kutubxonasi topilmadi. pip install pywin32")
else:
    HAS_WIN32PRINT = False


# ============================================================
# ESC/POS KOMANDALAR
# ============================================================

class ESCPOSCommands:
    """Xprinter va boshqa termal printerlar uchun ESC/POS komandalar"""

    # Printer boshqarish
    INIT = b'\x1b\x40'              # Printer reset
    CUT = b'\x1d\x56\x00'           # Qog'ozni kesish (full cut)
    PARTIAL_CUT = b'\x1d\x56\x01'   # Qisman kesish
    FEED_3 = b'\x1b\x64\x03'        # 3 qator bo'sh joy

    # Matn formatlash
    BOLD_ON = b'\x1b\x45\x01'
    BOLD_OFF = b'\x1b\x45\x00'
    UNDERLINE_ON = b'\x1b\x2d\x01'
    UNDERLINE_OFF = b'\x1b\x2d\x00'

    # Tekislash
    ALIGN_LEFT = b'\x1b\x61\x00'
    ALIGN_CENTER = b'\x1b\x61\x01'
    ALIGN_RIGHT = b'\x1b\x61\x02'

    # Shrift o'lchami
    FONT_NORMAL = b'\x1d\x21\x00'    # 1x1
    FONT_DOUBLE_H = b'\x1d\x21\x01'  # 1x2 (balandligi 2x)
    FONT_DOUBLE_W = b'\x1d\x21\x10'  # 2x1 (kengligi 2x)
    FONT_DOUBLE = b'\x1d\x21\x11'    # 2x2 (katta)

    # Encoding
    SET_CP866 = b'\x1b\x74\x11'      # CP866 (Kirill)
    SET_CP1252 = b'\x1b\x74\x10'     # Windows-1252 (Latin)


# ============================================================
# RECEIPT YARATISH
# ============================================================

class ReceiptBuilder:
    """Chop etish uchun receipt yaratuvchi"""

    def __init__(self, paper_width=80, encoding='cp866'):
        self.paper_width = paper_width
        self.encoding = encoding  # cp866 kirill + lotin uchun, utf-8 fallback
        # 80mm = ~42 belgi, 58mm = ~32 belgi
        self.char_width = 42 if paper_width == 80 else 32
        self.commands = bytearray()
        self.text_content = []  # Matnli versiya (log uchun)

    def init_printer(self):
        self.commands.extend(ESCPOSCommands.INIT)
        if self.encoding == 'cp866':
            self.commands.extend(ESCPOSCommands.SET_CP866)
        else:
            self.commands.extend(ESCPOSCommands.SET_CP1252)
        return self

    def add_text(self, text, bold=False, center=False, double=False, encoding=None):
        if center:
            self.commands.extend(ESCPOSCommands.ALIGN_CENTER)
        else:
            self.commands.extend(ESCPOSCommands.ALIGN_LEFT)

        if bold:
            self.commands.extend(ESCPOSCommands.BOLD_ON)
        if double:
            self.commands.extend(ESCPOSCommands.FONT_DOUBLE)

        # Encoding: cp866 (kirill/lotin) yoki utf-8 fallback
        enc = encoding or self.encoding
        self.commands.extend(text.encode(enc, errors='replace'))
        self.commands.extend(b'\n')
        self.text_content.append(text)

        if bold:
            self.commands.extend(ESCPOSCommands.BOLD_OFF)
        if double:
            self.commands.extend(ESCPOSCommands.FONT_NORMAL)

        return self

    def add_line(self, char='-'):
        line = char * self.char_width
        self.commands.extend(ESCPOSCommands.ALIGN_LEFT)
        self.commands.extend(line.encode(self.encoding, errors='replace'))
        self.commands.extend(b'\n')
        self.text_content.append(line)
        return self

    def add_double_line(self):
        return self.add_line('=')

    def add_item_line(self, name, qty, price):
        """Taom qatori: nom    x2    40,000"""
        price_str = f"{price:,.0f}".replace(',', ' ')
        qty_str = f"x{qty}"
        # nom uchun joy
        right_part = f"{qty_str:>5} {price_str:>10}"
        name_width = self.char_width - len(right_part) - 1
        if len(name) > name_width:
            name = name[:name_width - 2] + '..'
        line = f"  {name:<{name_width}}{right_part}"
        self.commands.extend(ESCPOSCommands.ALIGN_LEFT)
        self.commands.extend(line.encode(self.encoding, errors='replace'))
        self.commands.extend(b'\n')
        self.text_content.append(line)
        return self

    def add_modifier_line(self, name, qty, price):
        """Qo'shimcha mahsulot qatori:  + Non  x1  5,000"""
        price_str = f"{price:,.0f}".replace(',', ' ') if price > 0 else ''
        qty_str = f"x{qty}"
        prefix = "   +"
        if price_str:
            right_part = f"{qty_str:>4} {price_str:>10}"
        else:
            right_part = f"{qty_str:>4}"
        name_width = self.char_width - len(prefix) - len(right_part) - 1
        if len(name) > name_width:
            name = name[:name_width - 2] + '..'
        line = f"{prefix} {name:<{name_width}}{right_part}"
        self.commands.extend(ESCPOSCommands.ALIGN_LEFT)
        self.commands.extend(line.encode(self.encoding, errors='replace'))
        self.commands.extend(b'\n')
        self.text_content.append(line)
        return self

    def add_empty_line(self):
        self.commands.extend(b'\n')
        self.text_content.append('')
        return self

    def cut(self):
        self.commands.extend(ESCPOSCommands.FEED_3)
        self.commands.extend(ESCPOSCommands.CUT)
        return self

    def get_bytes(self):
        return bytes(self.commands)

    def get_text(self):
        return '\n'.join(self.text_content)


# ============================================================
# RECEIPT FORMATLASH
# ============================================================

def _render_items_block(rb, items):
    """Mahsulotlar + modifierlarni chekka yozish. Jami summani qaytaradi."""
    total = 0
    for item in items:
        name = item.get('name', 'Nomsiz')
        qty = int(item.get('quantity', 1))
        price = float(item.get('price', 0))
        item_total = qty * price
        total += item_total
        rb.add_item_line(name, qty, item_total)
        for mod in item.get('modifiers', []):
            mod_name = mod.get('name', '')
            mod_qty = int(mod.get('quantity', 1))
            mod_price = float(mod.get('price', 0))
            mod_total = mod_qty * mod_price
            total += mod_total
            rb.add_modifier_line(mod_name, mod_qty, mod_total)
    return total

# Buyurtma turini ReceiptTemplate.template_type ga moslashtirish
_ORDER_TYPE_MAP = {
    'DELIVERY': 'delivery',
    'YETKAZIB_BERISH': 'delivery',
    'YETKAZISH': 'delivery',
    'PICKUP': 'pickup',
    'OLIB_KETISH': 'pickup',
    'OLIB KETISH': 'pickup',
    'TAKEAWAY': 'pickup',
    'DINE_IN': 'dine_in',
    'ZALDA': 'dine_in',
    'ICHIDA': 'dine_in',
}


def _get_receipt_template(business_id, order_data, is_admin=False):
    """Buyurtma turiga qarab chek shablonini olish.
    Admin printer uchun avval 'admin' turini qidiradi."""
    # Admin printer uchun avval admin shablonni qidirish
    if is_admin:
        try:
            return ReceiptTemplate.objects.get(business_id=business_id, template_type='admin')
        except ReceiptTemplate.DoesNotExist:
            pass  # admin shabloni yo'q — oddiy turga fallback

    order_type = (order_data.get('order_type', '') or order_data.get('delivery_method', '')).strip().upper()
    scheduled = order_data.get('scheduled_time', '').strip()

    base_type = _ORDER_TYPE_MAP.get(order_type, 'delivery')

    # Reja buyurtma bo'lsa — avval sched_ versiyasini qidirish
    if scheduled:
        sched_type = 'sched_del' if base_type == 'delivery' else 'sched_pick'
        try:
            return ReceiptTemplate.objects.get(business_id=business_id, template_type=sched_type)
        except ReceiptTemplate.DoesNotExist:
            pass  # sched_ topilmasa oddiy turga fallback

    # Oddiy tur bo'yicha qidirish
    try:
        return ReceiptTemplate.objects.get(business_id=business_id, template_type=base_type)
    except ReceiptTemplate.DoesNotExist:
        return None


def build_kitchen_receipt(printer, order_data, items, other_printer_items=None, template=None):
    """Oshxona printer uchun receipt yaratish

    Args:
        printer: Printer model instance
        order_data: dict {order_id, order_number, business_name, customer_name,
                         customer_phone, customer_address, delivery_method, payment_method}
        items: list [{name, quantity, price, category_id, category_name}]
        other_printer_items: dict {printer_name: [items]} - boshqa printerlardagi mahsulotlar
        template: ReceiptTemplate instance (optional)
    """
    rb = ReceiptBuilder(paper_width=printer.paper_width)
    rb.init_printer()

    now = datetime.now().strftime('%d.%m.%Y %H:%M')

    # === SARLAVHA (ixcham) ===
    if template and template.header_text:
        business_name = template.header_text
    else:
        business_name = order_data.get('business_name', 'NONBOR')
    rb.add_text(business_name, bold=True, center=True, double=True)
    order_num = order_data.get('order_number', str(order_data.get('order_id', '')))
    rb.add_text(f"Nonbor #{order_num}  |  {now}", center=True)
    rb.add_line()

    # === STATUS (buyurtma turi) ===
    order_type = order_data.get('order_type', '').strip().upper()
    delivery_method = order_data.get('delivery_method', '').strip().upper()
    otype = order_type or delivery_method

    if otype in ('DELIVERY', 'YETKAZIB_BERISH', 'YETKAZISH'):
        status_text = ">> YETKAZIB BERISH <<"
    elif otype in ('PICKUP', 'OLIB_KETISH', 'OLIB KETISH', 'TAKEAWAY'):
        status_text = ">> OLIB KETISH <<"
    elif otype in ('DINE_IN', 'ZALDA', 'ICHIDA'):
        status_text = ">> ZALDA <<"
    elif otype:
        status_text = f">> {otype} <<"
    else:
        status_text = ""

    if status_text:
        rb.add_text(status_text, bold=True, center=True, double=True)

    # === REJA BUYURTMA ===
    scheduled_time = order_data.get('scheduled_time', '').strip()
    if scheduled_time:
        rb.add_text("*** REJA BUYURTMA ***", bold=True, center=True, double=True)
        rb.add_text(f"Vaqti: {scheduled_time}", bold=True, center=True)

    rb.add_line()

    # === MAHSULOTLAR (printer nomi bilan guruhlangan) ===
    is_admin = getattr(printer, 'is_admin', False)
    show_other = template.show_other_printers if template else True

    grand_total = 0

    if is_admin and other_printer_items:
        # Admin printer — faqat boshqa printerlar bo'yicha guruhlangan ro'yxat
        for other_name, other_items in other_printer_items.items():
            rb.add_text(f"[ {other_name} ]", bold=True, center=True)
            grand_total += _render_items_block(rb, other_items)
    else:
        # Oddiy printer — o'z mahsulotlari printer nomi bilan
        rb.add_text(f"[ {printer.name} ]", bold=True, center=True)
        grand_total += _render_items_block(rb, items)

        # Boshqa printerlarning mahsulotlari
        if other_printer_items and show_other:
            for other_name, other_items in other_printer_items.items():
                rb.add_text(f"[ {other_name} ]", bold=True, center=True)
                grand_total += _render_items_block(rb, other_items)

    # JAMI — eng oxirida
    rb.add_line()
    total_str = f"{grand_total:,.0f}".replace(',', ' ')
    jami_label = "JAMI:"
    jami_value = f"{total_str} so'm"
    jami_pad = rb.char_width - len(jami_label) - len(jami_value)
    if jami_pad < 1:
        jami_pad = 1
    rb.add_text(f"{jami_label}{' ' * jami_pad}{jami_value}", bold=True)

    rb.add_line()

    # Mijoz info
    show_customer = template.show_customer_info if template else True
    if show_customer:
        customer = order_data.get('customer_name', '')
        phone = order_data.get('customer_phone', '')
        address = order_data.get('customer_address', '')

        if customer:
            rb.add_text(f"Mijoz: {customer}")
        if phone:
            rb.add_text(f"Tel: {phone}")
        if address:
            rb.add_text(f"Manzil: {address}", bold=True)

    # Mijozning izohi
    show_comment = template.show_comment if template else True
    comment = order_data.get('comment', '').strip()
    if comment and show_comment:
        rb.add_double_line()
        rb.add_text("! IZOH:", bold=True)
        rb.add_text(comment, bold=True)

    # Footer matn (default: Rahmat!)
    footer = (template.footer_text if template and template.footer_text else 'Rahmat!')
    rb.add_line()
    rb.add_text(footer, center=True, bold=True)

    rb.add_double_line()
    rb.add_empty_line()
    rb.cut()

    return rb


# ============================================================
# PRINTERGA YUBORISH
# ============================================================

def send_to_network_printer(ip, port, data: bytes, timeout=5):
    """Tarmoq printer (TCP/IP) orqali chop etish"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((ip, port))
            sock.sendall(data)
        finally:
            sock.close()
        return True, None
    except socket.timeout:
        return False, f"Printer javob bermadi (timeout {timeout}s): {ip}:{port}"
    except ConnectionRefusedError:
        return False, f"Printer ulanishni rad etdi: {ip}:{port}"
    except OSError as e:
        return False, f"Tarmoq xatoligi: {ip}:{port} - {str(e)}"


def send_to_usb_printer(usb_path, data: bytes):
    """USB printer orqali chop etish.

    Windows da: usb_path = printer nomi (masalan: "PrinterPOS-80")
                win32print orqali RAW data yuboriladi
    Linux da:   usb_path = device path (masalan: "/dev/usb/lp0")
                to'g'ridan-to'g'ri file yozish
    """
    if IS_WINDOWS:
        return _send_to_windows_printer(usb_path, data)
    else:
        return _send_to_linux_usb(usb_path, data)


def _send_to_windows_printer(printer_name, data: bytes):
    """Windows USB/lokal printer - win32print orqali RAW chop etish"""
    if not HAS_WIN32PRINT:
        return False, "win32print kutubxonasi o'rnatilmagan. pip install pywin32"

    try:
        handle = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(handle, 1, ("Nonbor Receipt", None, "RAW"))
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
            win32print.EndDocPrinter(handle)
            return True, None
        finally:
            win32print.ClosePrinter(handle)
    except Exception as e:
        error_msg = str(e)
        if 'specified printer' in error_msg.lower() or '1801' in error_msg:
            return False, f"Printer topilmadi: '{printer_name}'. Printer nomini tekshiring."
        return False, f"Windows printer xatolik: {printer_name} - {error_msg}"


def _send_to_linux_usb(usb_path, data: bytes):
    """Linux USB printer - /dev/usb/lpX ga yozish"""
    try:
        with open(usb_path, 'wb') as f:
            f.write(data)
        return True, None
    except FileNotFoundError:
        return False, f"USB printer topilmadi: {usb_path}"
    except PermissionError:
        return False, f"USB printerga ruxsat yo'q: {usb_path}"
    except OSError as e:
        return False, f"USB xatolik: {usb_path} - {str(e)}"


def send_to_p8_printer(printer: Printer, data: bytes, timeout=10):
    """Trendit P8 Smart Cloud Printer orqali chop etish.

    Trendit P8 API ga ESC/POS ma'lumotini base64 formatida yuboradi.
    API javob: {"code": 0, "msg": "success"} yoki {"code": ..., "msg": "..."}
    """
    import base64

    if not printer.p8_device_sn:
        return False, "P8 qurilma SN ko'rsatilmagan"
    if not printer.p8_key:
        return False, "P8 API kaliti ko'rsatilmagan"

    api_url = (printer.p8_api_url or 'https://api.trenditen.com').rstrip('/')
    endpoint = f"{api_url}/open/print"

    payload = {
        'sn': printer.p8_device_sn,
        'key': printer.p8_key,
        'content': base64.b64encode(data).decode('utf-8'),
        'times': 1,
    }

    try:
        resp = _requests.post(endpoint, json=payload, timeout=timeout)
        resp.raise_for_status()
        result = resp.json()
        code = result.get('code', -1)
        if code == 0:
            return True, None
        msg = result.get('msg', 'Noma\'lum xatolik')
        return False, f"P8 API xatolik (code={code}): {msg}"
    except _requests.Timeout:
        return False, f"P8 API javob bermadi (timeout {timeout}s)"
    except _requests.ConnectionError as e:
        return False, f"P8 API ulanish xatoligi: {str(e)}"
    except _requests.HTTPError as e:
        return False, f"P8 API HTTP xatolik: {str(e)}"
    except Exception as e:
        return False, f"P8 xatolik: {str(e)}"


def send_to_printer(printer: Printer, data: bytes):
    """Printerga yuborish (auto-detect connection type)"""
    if printer.connection_type == Printer.CONNECTION_CLOUD:
        # Cloud rejim - printerga yuborilmaydi, agent o'zi olib ketadi
        # PrintJob "pending" holatda qoladi, agent poll qilib oladi
        return 'cloud', None
    elif printer.connection_type == Printer.CONNECTION_P8:
        return send_to_p8_printer(printer, data)
    elif printer.connection_type in (Printer.CONNECTION_NETWORK, Printer.CONNECTION_WIFI):
        if not printer.ip_address:
            return False, "IP manzil ko'rsatilmagan"
        return send_to_network_printer(printer.ip_address, printer.port, data)
    elif printer.connection_type == Printer.CONNECTION_USB:
        if not printer.usb_path:
            return False, "USB path ko'rsatilmagan"
        return send_to_usb_printer(printer.usb_path, data)
    else:
        return False, f"Noma'lum ulanish turi: {printer.connection_type}"


def detect_system_printers():
    """Tizimda o'rnatilgan printerlarni aniqlash"""
    printers = []

    # Windows - win32print orqali
    if IS_WINDOWS and HAS_WIN32PRINT:
        try:
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printer_list = win32print.EnumPrinters(flags, None, 2)
            default_printer = win32print.GetDefaultPrinter()

            for p in printer_list:
                name = p['pPrinterName']
                # Virtual printerlarni o'tkazib yuborish
                skip_names = ['Microsoft', 'OneNote', 'Fax', 'PDF', 'XPS', 'Send To']
                if any(s.lower() in name.lower() for s in skip_names):
                    continue

                port = p.get('pPortName', '')
                status_code = p.get('Status', 0)
                is_ready = status_code == 0

                # Ulanish turini aniqlash
                conn_type = 'usb'
                ip_address = ''
                printer_port = 9100
                if port and ':' in port and any(c.isdigit() for c in port.split(':')[0].split('.')):
                    # IP:port formatida - tarmoq printer
                    parts = port.split(':')
                    ip_address = parts[0]
                    printer_port = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 9100
                    conn_type = 'network'
                elif port and port.startswith('USB'):
                    conn_type = 'usb'

                printers.append({
                    'name': name,
                    'port_name': port,
                    'connection_type': conn_type,
                    'ip_address': ip_address,
                    'printer_port': printer_port,
                    'is_default': name == default_printer,
                    'is_ready': is_ready,
                    'driver': p.get('pDriverName', ''),
                    'status': 'ready' if is_ready else 'offline',
                })
        except Exception as e:
            logger.error(f"Windows printer aniqlash xatosi: {e}")

    # Linux - lpstat orqali
    elif not IS_WINDOWS:
        import subprocess
        try:
            result = subprocess.run(['lpstat', '-p', '-d'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('printer '):
                        parts = line.split()
                        name = parts[1]
                        is_ready = 'idle' in line.lower() or 'enabled' in line.lower()
                        printers.append({
                            'name': name,
                            'port_name': '',
                            'connection_type': 'usb',
                            'ip_address': '',
                            'printer_port': 9100,
                            'is_default': False,
                            'is_ready': is_ready,
                            'driver': '',
                            'status': 'ready' if is_ready else 'offline',
                        })

            # Default printer
            for line in result.stdout.split('\n'):
                if 'system default' in line.lower():
                    default_name = line.split(':')[-1].strip()
                    for p in printers:
                        if p['name'] == default_name:
                            p['is_default'] = True
        except Exception as e:
            logger.error(f"Linux printer aniqlash xatosi: {e}")

    # Tarmoqdagi printerlarni ham qidirish (port 9100 - concurrent scan)
    try:
        import concurrent.futures
        local_ip = socket.gethostbyname(socket.gethostname())
        subnet = '.'.join(local_ip.split('.')[:3])
        known_ips = {p['ip_address'] for p in printers if p.get('ip_address')}

        def check_port(ip):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.15)
                result = sock.connect_ex((ip, 9100))
                sock.close()
                return ip if result == 0 else None
            except:
                return None

        ips_to_scan = [f"{subnet}.{i}" for i in range(1, 255) if f"{subnet}.{i}" not in known_ips]
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = executor.map(check_port, ips_to_scan)
            for ip in results:
                if ip:
                    printers.append({
                        'name': f"Tarmoq printer ({ip})",
                        'port_name': f"{ip}:9100",
                        'connection_type': 'network',
                        'ip_address': ip,
                        'printer_port': 9100,
                        'is_default': False,
                        'is_ready': True,
                        'driver': 'TCP/IP',
                        'status': 'ready',
                    })
    except Exception as e:
        logger.debug(f"Tarmoq scan xatosi: {e}")

    return printers


# ============================================================
# JOB YARATISH VA YUBORISH
# ============================================================

def _create_and_send_job(printer, receipt, order_data, items_data, business_id):
    """PrintJob yaratish, printerga yuborish, natijani qayd qilish."""
    job = PrintJob.objects.create(
        printer=printer,
        order_id=order_data.get('order_id', 0),
        business_id=business_id,
        status=PrintJob.STATUS_PENDING,
        content=receipt.get_text(),
        items_data=items_data,
    )

    result, error = send_to_printer(printer, receipt.get_bytes())
    order_id = order_data.get('order_id')

    if result == 'cloud':
        logger.info(f"Buyurtma #{order_id} -> {printer.name}: agent kutilmoqda")
    elif result:
        job.mark_completed()
        logger.info(f"Buyurtma #{order_id} -> {printer.name}: chop etildi")
    else:
        job.mark_failed(error)
        logger.error(f"Buyurtma #{order_id} -> {printer.name}: XATOLIK - {error}")
        _notify_failure(job, error)

    return job


def _notify_failure(job, error):
    """Print job xatoligini bildirishnoma sifatida yuborish"""
    try:
        from .notification_service import notify_print_failure
        notify_print_failure(job, error)
    except Exception as e:
        logger.error(f"Bildirishnoma yuborib bo'lmadi: {e}")


# ============================================================
# ASOSIY PRINT SERVICE
# ============================================================

def print_order(order_data, items, business_id):
    """Buyurtmani barcha tegishli printerlarga chop etish.

    Ustunlik tartibi:
    1. product_id bo'yicha (PrinterProduct) - ENG YUQORI
    2. category_id bo'yicha (PrinterCategory)
    3. Default printer (birinchi aktiv)

    Args:
        order_data: dict {order_id, order_number, business_name,
                         customer_name, customer_phone, customer_address,
                         delivery_method, payment_method}
        items: list [{name, quantity, price, product_id, category_id, category_name}]
        business_id: int

    Returns:
        list of PrintJob instances
    """
    # Chek shablonini yuklash (buyurtma turiga qarab)
    template = _get_receipt_template(business_id, order_data)
    admin_template = _get_receipt_template(business_id, order_data, is_admin=True)
    # 1. Product → Printer mapping (ENG YUQORI USTUNLIK)
    product_printer_map = {}
    product_mappings = PrinterProduct.objects.filter(
        business_id=business_id,
        printer__is_active=True,
    ).select_related('printer')
    for mapping in product_mappings:
        product_printer_map[mapping.product_id] = mapping.printer

    # 2. Category → Printer mapping
    category_printer_map = {}
    category_mappings = PrinterCategory.objects.filter(
        business_id=business_id,
        printer__is_active=True,
    ).select_related('printer')
    for mapping in category_mappings:
        category_printer_map[mapping.category_id] = mapping.printer

    # 3. Har bir taom uchun printer aniqlash
    printer_items = defaultdict(list)
    unassigned_items = []

    for item in items:
        product_id = item.get('product_id')
        cat_id = item.get('category_id')

        # Avval product_id bo'yicha qidiramiz
        printer = product_printer_map.get(product_id) if product_id else None

        # Topilmasa - category_id bo'yicha
        if not printer and cat_id:
            printer = category_printer_map.get(cat_id)

        if printer:
            printer_items[printer.id].append(item)
        else:
            unassigned_items.append(item)

    # Ulashilmagan taomlar - birinchi aktiv non-admin printerga yuborish
    if unassigned_items:
        default_printer = Printer.objects.filter(
            business_id=business_id,
            is_active=True,
            is_admin=False,
        ).first()
        if default_printer:
            printer_items[default_printer.id].extend(unassigned_items)
            logger.warning(
                f"Ulashilmagan {len(unassigned_items)} ta taom "
                f"default printerga ({default_printer.name}) yuborildi"
            )
        else:
            logger.warning(
                f"Biznes #{business_id}: printer biriktirilmagan, "
                f"{len(unassigned_items)} ta taom chop etilmadi"
            )

    # 4. Admin printerlar - barcha buyurtmalarni umumiy oladi
    admin_printers = Printer.objects.filter(
        business_id=business_id,
        is_active=True,
        is_admin=True,
    )

    # 5. Har bir printer uchun receipt yaratish va yuborish
    print_jobs = []
    all_printer_ids = set(printer_items.keys()) | {p.id for p in admin_printers}
    printers = {p.id: p for p in Printer.objects.filter(id__in=all_printer_ids)}

    # Admin printerlar uchun barcha itemlarni qo'shish
    for admin_p in admin_printers:
        if admin_p.id not in printer_items:
            # Admin printer hali ro'yxatda yo'q - barcha itemlarni berish
            printer_items[admin_p.id] = list(items)
        else:
            # Admin printer allaqachon ba'zi itemlarga ulangan
            # Qolgan itemlarni ham qo'shish
            existing_ids = {(i.get('product_id'), i.get('name')) for i in printer_items[admin_p.id]}
            for item in items:
                key = (item.get('product_id'), item.get('name'))
                if key not in existing_ids:
                    printer_items[admin_p.id].append(item)

    # Avval oddiy printerlarni chop etish (admin emas)
    # Keyin admin printerlarga failed/success ma'lumotlari bilan receipt yaratish
    printer_results = {}  # {printer_name: 'ok' | 'failed' | 'pending'}
    admin_printer_ids = {p.id for p in admin_printers}

    # 5a. Oddiy printerlar
    for printer_id, p_items in printer_items.items():
        printer = printers.get(printer_id)
        if not printer or printer.is_admin:
            continue

        other_printer_items = {}
        for other_pid, other_items in printer_items.items():
            if other_pid == printer_id:
                continue
            other_printer = printers.get(other_pid)
            if other_printer and not other_printer.is_admin:
                other_printer_items[other_printer.name] = other_items

        receipt = build_kitchen_receipt(
            printer, order_data, p_items, other_printer_items, template=template
        )

        job = _create_and_send_job(printer, receipt, order_data, p_items, business_id)
        if job.status == PrintJob.STATUS_FAILED:
            printer_results[printer.name] = 'failed'
        elif job.status == PrintJob.STATUS_PENDING:
            printer_results[printer.name] = 'pending'
        else:
            printer_results[printer.name] = 'ok'
        print_jobs.append(job)

    # 5b. Admin printerlar — barcha maxsulotlar printer nomlari bilan
    for printer_id in list(printer_items.keys()):
        printer = printers.get(printer_id)
        if not printer or not printer.is_admin:
            continue

        p_items = printer_items[printer_id]

        # Admin uchun other_printer_items: oddiy printerlarning maxsulotlari + holati
        admin_other = {}
        for other_pid, other_items in printer_items.items():
            if other_pid == printer_id:
                continue
            other_printer = printers.get(other_pid)
            if other_printer and not other_printer.is_admin:
                pr_status = printer_results.get(other_printer.name, 'pending')
                suffix = {
                    'failed': ' - CHOP ETILMADI!',
                    'pending': ' - kutilmoqda',
                }.get(pr_status, '')
                admin_other[f"{other_printer.name}{suffix}"] = other_items

        receipt = build_kitchen_receipt(
            printer, order_data, p_items, admin_other, template=admin_template
        )
        job = _create_and_send_job(printer, receipt, order_data, p_items, business_id)
        print_jobs.append(job)

    return print_jobs


def retry_print_job(job: PrintJob):
    """Muvaffaqiyatsiz print jobni qayta urinish"""
    if not job.can_retry:
        return False, "Qayta urinishlar tugadi"

    printer = job.printer
    if not printer.is_active:
        return False, "Printer o'chirilgan"

    # Receipt qayta yaratish
    receipt = build_kitchen_receipt(
        printer,
        {
            'order_id': job.order_id,
            'business_name': '',
        },
        job.items_data,
    )

    job.status = PrintJob.STATUS_PRINTING
    job.save(update_fields=['status'])

    success, error = send_to_printer(printer, receipt.get_bytes())

    if success:
        job.mark_completed()
        return True, None
    else:
        job.mark_failed(error)
        _notify_failure(job, error)
        return False, error


def send_test_print(printer: Printer):
    """Test sahifa chop etish"""
    rb = ReceiptBuilder(paper_width=printer.paper_width)
    rb.init_printer()

    rb.add_double_line()
    rb.add_text("TEST SAHIFA", bold=True, center=True, double=True)
    rb.add_double_line()
    rb.add_empty_line()
    rb.add_text(f"Printer: {printer.name}", center=True)
    rb.add_text(f"Model: {printer.printer_model or 'Nomalum'}", center=True)
    rb.add_text(f"Ulanish: {printer.get_connection_type_display()}", center=True)

    if printer.connection_type in (Printer.CONNECTION_NETWORK, Printer.CONNECTION_WIFI):
        rb.add_text(f"IP: {printer.ip_address}:{printer.port}", center=True)
    elif printer.connection_type == Printer.CONNECTION_USB:
        rb.add_text(f"USB: {printer.usb_path}", center=True)
    else:
        rb.add_text(f"Cloud: Agent orqali", center=True)

    rb.add_text(f"Qog'oz: {printer.paper_width}mm", center=True)
    rb.add_empty_line()

    now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    rb.add_text(f"Sana: {now}", center=True)
    rb.add_empty_line()
    rb.add_text("Printer muvaffaqiyatli ishlayapti!", center=True, bold=True)
    rb.add_double_line()
    rb.add_empty_line()
    rb.cut()

    return send_to_printer(printer, rb.get_bytes())
