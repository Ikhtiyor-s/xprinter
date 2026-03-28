#!/usr/bin/env python3
"""
Nonbor Print Agent - Oshxonaga o'rnatiladigan chop etish agenti.

Bu skript oshxonadagi kompyuter/planshetda ishga tushiriladi.
Har 3 soniyada serverdan yangi print joblarni tekshiradi
va lokal printerlarga chop etadi.

Ishga tushirish:
    python print_agent.py

Sozlamalar:
    SERVER_URL  - Nonbor backend URL
    BUSINESS_ID - Biznes ID
    USERNAME    - API login
    PASSWORD    - API parol
    POLL_INTERVAL - Tekshirish oralig'i (soniya)
"""

import os
import sys
import time
import socket
import logging
import json
from datetime import datetime

# ============================================================
# SOZLAMALAR - OSHXONA UCHUN O'ZGARTIRING
# ============================================================

SERVER_URL = os.environ.get('PRINT_SERVER_URL', 'http://localhost:9000')
BUSINESS_ID = os.environ.get('PRINT_BUSINESS_ID', '1')
USERNAME = os.environ.get('PRINT_USERNAME', 'admin')
PASSWORD = os.environ.get('PRINT_PASSWORD', 'admin123')
POLL_INTERVAL = int(os.environ.get('PRINT_POLL_INTERVAL', '3'))  # soniya

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('print_agent')

# ============================================================
# HTTP CLIENT (requests kutubxonasisiz)
# ============================================================

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

if not HAS_REQUESTS:
    import urllib.request
    import urllib.error
    import base64


def api_get(path, params=None):
    """GET so'rov"""
    url = f"{SERVER_URL}/api/v2/{path}"
    if params:
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        url += f'?{query}'

    if HAS_REQUESTS:
        resp = requests.get(url, auth=(USERNAME, PASSWORD), timeout=10)
        return resp.json()
    else:
        req = urllib.request.Request(url)
        creds = base64.b64encode(f'{USERNAME}:{PASSWORD}'.encode()).decode()
        req.add_header('Authorization', f'Basic {creds}')
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())


def api_post(path, data):
    """POST so'rov"""
    url = f"{SERVER_URL}/api/v2/{path}"
    body = json.dumps(data).encode()

    if HAS_REQUESTS:
        resp = requests.post(
            url, json=data,
            auth=(USERNAME, PASSWORD), timeout=10,
        )
        return resp.json()
    else:
        req = urllib.request.Request(url, data=body, method='POST')
        creds = base64.b64encode(f'{USERNAME}:{PASSWORD}'.encode()).decode()
        req.add_header('Authorization', f'Basic {creds}')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())


# ============================================================
# ESC/POS KOMANDALAR
# ============================================================

ESC_INIT = b'\x1b\x40'
ESC_CUT = b'\x1d\x56\x00'
ESC_FEED = b'\x1b\x64\x03'
ESC_BOLD_ON = b'\x1b\x45\x01'
ESC_BOLD_OFF = b'\x1b\x45\x00'
ESC_CENTER = b'\x1b\x61\x01'
ESC_LEFT = b'\x1b\x61\x00'
ESC_FONT_DOUBLE = b'\x1d\x21\x11'
ESC_FONT_NORMAL = b'\x1d\x21\x00'


def text_to_escpos(text, paper_width=80):
    """Matnni ESC/POS formatga o'girish"""
    commands = bytearray()
    commands.extend(ESC_INIT)

    char_width = 42 if paper_width == 80 else 32

    for line in text.split('\n'):
        # Qalin matn (JAMI, Buyurtma, Business nomi)
        is_bold = any(w in line for w in ['JAMI:', 'Buyurtma:', 'Printer:', '===='])

        if '====' in line:
            commands.extend(ESC_LEFT)
            commands.extend(('=' * char_width).encode('utf-8'))
        elif '----' in line:
            commands.extend(ESC_LEFT)
            commands.extend(('-' * char_width).encode('utf-8'))
        else:
            if is_bold:
                commands.extend(ESC_BOLD_ON)
            commands.extend(ESC_LEFT)
            commands.extend(line.encode('utf-8', errors='replace'))
            if is_bold:
                commands.extend(ESC_BOLD_OFF)

        commands.extend(b'\n')

    commands.extend(ESC_FEED)
    commands.extend(ESC_CUT)
    return bytes(commands)


# ============================================================
# PRINTERGA YUBORISH
# ============================================================

IS_WINDOWS = sys.platform == 'win32'

if IS_WINDOWS:
    try:
        import win32print
        HAS_WIN32 = True
    except ImportError:
        HAS_WIN32 = False
else:
    HAS_WIN32 = False


def print_to_network(ip, port, data):
    """Tarmoq printer (TCP/IP)"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, port))
        sock.sendall(data)
        sock.close()
        return True, None
    except Exception as e:
        return False, str(e)


def print_to_usb_windows(printer_name, data):
    """Windows USB printer"""
    if not HAS_WIN32:
        return False, "pywin32 o'rnatilmagan"
    try:
        handle = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(handle, 1, ("Nonbor Agent", None, "RAW"))
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
            win32print.EndDocPrinter(handle)
            return True, None
        finally:
            win32print.ClosePrinter(handle)
    except Exception as e:
        return False, str(e)


def print_to_usb_linux(path, data):
    """Linux USB printer"""
    try:
        with open(path, 'wb') as f:
            f.write(data)
        return True, None
    except Exception as e:
        return False, str(e)


def print_job(job):
    """Print jobni chop etish"""
    content = job.get('content', '')
    paper_width = job.get('paper_width', 80)
    conn_type = job.get('printer_connection', 'cloud')
    printer_ip = job.get('printer_ip')
    printer_port = job.get('printer_port', 9100)
    printer_usb = job.get('printer_usb', '')

    # ESC/POS formatga o'girish
    data = text_to_escpos(content, paper_width)

    # Chop etish
    if conn_type in ('network', 'wifi') and printer_ip:
        return print_to_network(printer_ip, printer_port, data)
    elif conn_type in ('usb', 'cloud') and printer_usb:
        if IS_WINDOWS:
            return print_to_usb_windows(printer_usb, data)
        else:
            return print_to_usb_linux(printer_usb, data)
    elif conn_type == 'cloud':
        # Cloud printer - lokal printerlarni qidirish
        # Agent config da belgilangan default printer
        default_printer = os.environ.get('PRINT_DEFAULT_PRINTER', '')
        if default_printer:
            if IS_WINDOWS:
                return print_to_usb_windows(default_printer, data)
            else:
                return print_to_usb_linux(default_printer, data)
        return False, "Lokal printer sozlanmagan (PRINT_DEFAULT_PRINTER)"
    else:
        return False, f"Printer sozlamalari to'liq emas: conn={conn_type}"


# ============================================================
# ASOSIY LOOP
# ============================================================

def poll_and_print():
    """Serverdan joblarni olish va chop etish"""
    try:
        response = api_get('print-job/agent/poll/', {'business_id': BUSINESS_ID})
    except Exception as e:
        logger.error(f"Server bilan bog'lanib bo'lmadi: {e}")
        return

    if not response.get('success'):
        err = response.get('error', 'Nomalum')
        logger.error(f"Server xatolik: {err}")
        return

    jobs = response.get('result', [])
    if not jobs:
        return  # Hech narsa yo'q

    logger.info(f"{len(jobs)} ta yangi job topildi")

    for job in jobs:
        job_id = job['id']
        order_id = job['order_id']
        printer_name = job['printer_name']

        logger.info(f"  Chop etilmoqda: #{order_id} → {printer_name}")

        success, error = print_job(job)

        # Serverga natija yuborish
        try:
            if success:
                api_post('print-job/agent/complete/', {
                    'job_id': job_id,
                    'status': 'completed',
                })
                logger.info(f"  ✓ #{order_id} → {printer_name} - TAYYOR")
            else:
                api_post('print-job/agent/complete/', {
                    'job_id': job_id,
                    'status': 'failed',
                    'error': error or 'Nomalum xatolik',
                })
                logger.error(f"  ✗ #{order_id} → {printer_name} - {error}")
        except Exception as e:
            logger.error(f"  Serverga javob yuborib bo'lmadi: {e}")


def main():
    print("=" * 50)
    print("  NONBOR PRINT AGENT")
    print("=" * 50)
    print(f"  Server:      {SERVER_URL}")
    print(f"  Business ID: {BUSINESS_ID}")
    print(f"  Interval:    {POLL_INTERVAL}s")
    print(f"  Platform:    {'Windows' if IS_WINDOWS else 'Linux'}")

    if IS_WINDOWS and HAS_WIN32:
        # Lokal printerlarni ko'rsatish
        printers = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
        pos_printers = [name for _, _, name, _ in printers
                        if any(kw in name.lower() for kw in ['pos', 'xprinter', 'thermal', 'receipt'])]
        if pos_printers:
            print(f"  Printerlar:  {', '.join(pos_printers)}")
        else:
            print(f"  Printerlar:  {[name for _, _, name, _ in printers]}")

    default = os.environ.get('PRINT_DEFAULT_PRINTER', '')
    if default:
        print(f"  Default:     {default}")

    print("=" * 50)
    print("  Ctrl+C bosib to'xtatish mumkin")
    print()

    # Serverga ulanishni tekshirish
    try:
        resp = api_get('printer/list/', {'business_id': BUSINESS_ID})
        printers = resp.get('result', [])
        logger.info(f"Server bilan bog'landi. {len(printers)} ta printer topildi.")
    except Exception as e:
        logger.error(f"Serverga ulanib bo'lmadi: {e}")
        logger.error("Sozlamalarni tekshiring va qayta urinib ko'ring.")
        sys.exit(1)

    # Asosiy loop
    logger.info("Agent ishga tushdi. Buyurtmalar kutilmoqda...")
    while True:
        try:
            poll_and_print()
        except KeyboardInterrupt:
            logger.info("Agent to'xtatildi.")
            break
        except Exception as e:
            logger.error(f"Kutilmagan xatolik: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
