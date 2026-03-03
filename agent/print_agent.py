#!/usr/bin/env python3
"""
Nonbor Print Agent v2.0 - Oshxonaga o'rnatiladigan chop etish agenti.

Bu skript oshxonadagi kompyuter/planshetda ishga tushiriladi.
Har N soniyada serverdan yangi print joblarni tekshiradi
va lokal printerga chop etadi.

Ishga tushirish:
    start.bat ni ikki marta bosing

Sozlamalar:
    config.ini faylida
"""

import os
import sys
import time
import socket
import logging
import json
import configparser
from datetime import datetime

# ============================================================
# CONFIG.INI DAN SOZLAMALARNI O'QISH
# ============================================================

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(AGENT_DIR, 'config.ini')

config = configparser.ConfigParser()

if os.path.exists(CONFIG_FILE):
    config.read(CONFIG_FILE, encoding='utf-8')
else:
    print(f"XATOLIK: config.ini topilmadi: {CONFIG_FILE}")
    print("Avval setup.bat ni ishga tushiring!")
    input("Enter bosib yoping...")
    sys.exit(1)

SERVER_URL = config.get('server', 'url', fallback='http://localhost:9000').rstrip('/')
BUSINESS_ID = config.get('business', 'id', fallback='1')
USERNAME = config.get('auth', 'username', fallback='admin')
PASSWORD = config.get('auth', 'password', fallback='admin123')
DEFAULT_PRINTER = config.get('printer', 'default_printer', fallback='')
POLL_INTERVAL = config.getint('settings', 'poll_interval', fallback=3)
PAPER_WIDTH = config.getint('settings', 'paper_width', fallback=80)

# ============================================================
# LOGGING (fayl + konsol)
# ============================================================

LOG_FILE = os.path.join(AGENT_DIR, 'agent.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger('print_agent')

# Windows konsol UTF-8
if sys.platform == 'win32':
    try:
        os.system('chcp 65001 >nul 2>&1')
    except Exception:
        pass

# ============================================================
# HTTP CLIENT
# ============================================================

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error
    import base64


def api_get(path, params=None):
    """GET so'rov"""
    url = f"{SERVER_URL}/{path}"
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
    url = f"{SERVER_URL}/{path}"
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


def get_windows_printers():
    """Windows dagi barcha printerlar ro'yxati"""
    if not HAS_WIN32:
        return []
    printers = win32print.EnumPrinters(
        win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    )
    return [name for _, _, name, _ in printers]


def find_pos_printer():
    """POS/thermal printerni avtomatik topish"""
    if not HAS_WIN32:
        return None
    printers = get_windows_printers()
    keywords = ['pos', 'xprinter', 'thermal', 'receipt', '80', '58']
    for name in printers:
        if any(kw in name.lower() for kw in keywords):
            return name
    return None


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
        return False, "pywin32 o'rnatilmagan. Buyruq: pip install pywin32"
    try:
        handle = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(handle, 1, ("Nonbor Order", None, "RAW"))
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


def do_print(job):
    """Print jobni chop etish"""
    content = job.get('content', '')
    pw = job.get('paper_width', PAPER_WIDTH)
    conn_type = job.get('printer_connection', 'cloud')
    printer_ip = job.get('printer_ip')
    printer_port = job.get('printer_port', 9100)
    printer_usb = job.get('printer_usb', '')

    # ESC/POS formatga o'girish
    data = text_to_escpos(content, pw)

    # Tarmoq printer
    if conn_type == 'network' and printer_ip:
        return print_to_network(printer_ip, printer_port, data)

    # USB printer (server ko'rsatgan)
    if printer_usb:
        if IS_WINDOWS:
            return print_to_usb_windows(printer_usb, data)
        else:
            return print_to_usb_linux(printer_usb, data)

    # Default printer (config.ini dan)
    target = DEFAULT_PRINTER
    if not target and IS_WINDOWS:
        target = find_pos_printer()

    if target:
        if IS_WINDOWS:
            return print_to_usb_windows(target, data)
        else:
            return print_to_usb_linux(target, data)

    return False, "Printer topilmadi. config.ini da default_printer ni belgilang."


# ============================================================
# ASOSIY LOOP
# ============================================================

def poll_and_print():
    """Serverdan joblarni olish va chop etish"""
    try:
        response = api_get('print-job/agent/poll/', {'business_id': BUSINESS_ID})
    except Exception as e:
        logger.error("Server bilan bog'lanib bo'lmadi: %s", e)
        return

    if not response.get('success'):
        err = response.get('error', 'Nomalum xatolik')
        logger.error("Server xatolik: %s", err)
        return

    jobs = response.get('result', [])
    if not jobs:
        return

    logger.info("%d ta yangi job topildi", len(jobs))

    for job in jobs:
        job_id = job['id']
        order_id = job.get('order_id', '?')
        printer_name = job.get('printer_name', '?')

        logger.info("  Chop etilmoqda: #%s -> %s", order_id, printer_name)

        success, error = do_print(job)

        # Serverga natija yuborish
        try:
            if success:
                api_post('print-job/agent/complete/', {
                    'job_id': job_id,
                    'status': 'completed',
                })
                logger.info("  OK #%s -> %s - TAYYOR", order_id, printer_name)
            else:
                api_post('print-job/agent/complete/', {
                    'job_id': job_id,
                    'status': 'failed',
                    'error': error or 'Nomalum xatolik',
                })
                logger.error("  XATO #%s -> %s - %s", order_id, printer_name, error)
        except Exception as e:
            logger.error("  Serverga javob yuborib bo'lmadi: %s", e)


def show_banner():
    """Dastur haqida ma'lumot"""
    print("=" * 50)
    print("  NONBOR PRINT AGENT v2.0")
    print("=" * 50)
    print(f"  Server:      {SERVER_URL}")
    print(f"  Business ID: {BUSINESS_ID}")
    print(f"  Interval:    {POLL_INTERVAL}s")
    print(f"  Platform:    {'Windows' if IS_WINDOWS else 'Linux'}")

    if IS_WINDOWS and HAS_WIN32:
        printers = get_windows_printers()
        pos = find_pos_printer()
        if printers:
            print(f"  Printerlar:  {', '.join(printers)}")
        if pos and not DEFAULT_PRINTER:
            print(f"  Auto-topildi: {pos}")

    if DEFAULT_PRINTER:
        print(f"  Default:     {DEFAULT_PRINTER}")

    print("=" * 50)
    print("  Ctrl+C bosib to'xtatish mumkin")
    print()


def check_server():
    """Serverga ulanishni tekshirish"""
    try:
        resp = api_get('printer/list/', {'business_id': BUSINESS_ID})
        printers = resp.get('result', [])
        logger.info("Server bilan bog'landi. %d ta printer topildi.", len(printers))
        return True
    except Exception as e:
        logger.error("Serverga ulanib bo'lmadi: %s", e)
        logger.error("config.ini dagi server URL va login/parolni tekshiring.")
        return False


def main():
    show_banner()

    if not check_server():
        print("\nServerga ulanib bo'lmadi. Sozlamalarni tekshiring.")
        input("Enter bosib yoping...")
        sys.exit(1)

    # Auto-detect printer if not set
    if not DEFAULT_PRINTER and IS_WINDOWS:
        auto = find_pos_printer()
        if auto:
            logger.info("POS printer avtomatik topildi: %s", auto)

    logger.info("Agent ishga tushdi. Buyurtmalar kutilmoqda...")

    while True:
        try:
            poll_and_print()
        except KeyboardInterrupt:
            logger.info("Agent to'xtatildi.")
            break
        except Exception as e:
            logger.error("Kutilmagan xatolik: %s", e)

        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
