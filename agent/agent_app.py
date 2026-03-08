#!/usr/bin/env python3
"""
Nonbor Print Agent v4.0
- Tray ikonida ishlaydi (fon rejim)
- GUI faqat sozlamalar uchun
- Batch fayllar kerak emas
"""

import os, sys, time, uuid, socket, json, threading, logging, configparser
from pathlib import Path
from datetime import datetime

# ── BASE DIR ────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    # EXE rejimda C:\NonborPrintAgent\ papkada ishlaydi
    BASE_DIR = Path('C:/NonborPrintAgent')
    BASE_DIR.mkdir(exist_ok=True)
    # PyInstaller EXE da SSL sertifikat yo'lini to'g'ri sozlash
    _cert_file = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')
    if os.path.exists(_cert_file):
        os.environ['SSL_CERT_FILE'] = _cert_file
        os.environ['REQUESTS_CA_BUNDLE'] = _cert_file
else:
    BASE_DIR = Path(__file__).parent

CONFIG_FILE        = BASE_DIR / 'config.ini'
PRINTERS_FILE      = BASE_DIR / 'printers.json'  # fallback (eski format)
LOG_FILE           = BASE_DIR / 'agent.log'
SAVED_LOGINS_FILE  = BASE_DIR / 'saved_logins.json'
PRODUCTS_CACHE     = BASE_DIR / 'products_cache.json'  # fallback (eski format)

def _printers_path(business_id=None):
    """Business ID bo'yicha alohida printers fayli"""
    if business_id:
        return BASE_DIR / f'printers_{business_id}.json'
    return PRINTERS_FILE

def _cache_path(business_id=None):
    """Business ID bo'yicha alohida products cache fayli"""
    if business_id:
        return BASE_DIR / f'products_cache_{business_id}.json'
    return PRODUCTS_CACHE

# ── SERVER URL (server_url.txt dan o'qiladi, aks holda default) ─────────
_SERVER_URL_FILE = BASE_DIR / 'server_url.txt'
_DEFAULT_SERVER = "https://scrubbier-shantae-vaunted.ngrok-free.dev"
def _load_server_url():
    if _SERVER_URL_FILE.exists():
        try:
            url = _SERVER_URL_FILE.read_text(encoding='utf-8').strip()
            if url: return url.rstrip('/')
        except: pass
    # Fayl yo'q — avtomatik yaratish
    try:
        _SERVER_URL_FILE.write_text(_DEFAULT_SERVER, encoding='utf-8')
    except Exception:
        pass
    return _DEFAULT_SERVER

SERVER_URL = _load_server_url()

# ── LOGGING ─────────────────────────────────────────────────
fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger = logging.getLogger('nonbor')
logger.setLevel(logging.INFO)
logger.addHandler(fh)

# ── PLATFORM ────────────────────────────────────────────────
IS_WIN = sys.platform == 'win32'
try:
    import win32print; HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import winreg; HAS_REG = True
except ImportError:
    HAS_REG = False

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

try:
    import requests as _req
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    HAS_REQ = True
except ImportError:
    HAS_REQ = False
    import urllib.request, base64

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# ── CONFIG ───────────────────────────────────────────────────
def _cfg_get(cfg, s, k, d=''):
    try: return cfg.get(s, k)
    except: return d

def load_config():
    c = configparser.ConfigParser()
    if CONFIG_FILE.exists(): c.read(CONFIG_FILE, encoding='utf-8')
    return c

def save_config(a):
    c = configparser.ConfigParser()
    c['business'] = {'id': a.business_id, 'name': getattr(a, 'business_name', '')}
    c['auth']     = {'username': a.username, 'password': a.password}
    c['settings'] = {'poll_interval': str(a.poll_interval),
                     'server_url': a.server_url}
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f: c.write(f)

def is_logged_in():
    c = load_config()
    return bool(_cfg_get(c, 'auth', 'username') and _cfg_get(c, 'business', 'id'))

def do_logout():
    """Faqat config o'chiriladi, printer sozlamalari saqlanib qoladi"""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()

def load_saved_logins():
    if SAVED_LOGINS_FILE.exists():
        try:
            with open(SAVED_LOGINS_FILE, encoding='utf-8') as f: return json.load(f)
        except: pass
    return []

def save_login_to_history(username):
    logins = [l for l in load_saved_logins() if l.get('username') != username]
    logins.insert(0, {'username': username})
    with open(SAVED_LOGINS_FILE, 'w', encoding='utf-8') as f:
        json.dump(logins[:10], f, ensure_ascii=False)

_NGROK_HEADER = {'ngrok-skip-browser-warning': 'true'}

def api_fetch_menu(server_url, username, password, business_id):
    """GET /api/v2/agent/menu/<business_id>/ → (ok, products, error)
    products: [{id, name, category_id, category_name}]"""
    try:
        full = f"{server_url}/api/v2/agent/menu/{business_id}/"
        params = {'username': username, 'password': password}
        if HAS_REQ:
            r = _req.get(full, params=params, headers=_NGROK_HEADER, timeout=60, verify=False)
            try: data = r.json()
            except: return False, [], f"Server xatosi ({r.status_code}): {r.text[:100]}"
        else:
            import urllib.parse, ssl
            qs = urllib.parse.urlencode(params)
            req = urllib.request.Request(f"{full}?{qs}")
            req.add_header('ngrok-skip-browser-warning', 'true')
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = json.loads(resp.read())
        if data.get('success'):
            return True, data.get('products', []), None
        return False, [], data.get('error', 'Noma\'lum xato')
    except Exception as e:
        logger.error(f"Menu fetch xato: {e}")
        return False, [], str(e)


def api_sync_printer(server_url, username, password, printer_data):
    """POST /api/v2/agent/printer-sync/ → (ok, printer_id, error)"""
    try:
        full = f"{server_url}/api/v2/agent/printer-sync/"
        payload = {
            'username': username,
            'password': password,
            'name': printer_data.get('name', ''),
            'connection_type': printer_data.get('connection', 'usb'),
            'ip': printer_data.get('ip', ''),
            'port': printer_data.get('port', 9100),
            'usb': printer_data.get('usb', ''),
            'paper_width': printer_data.get('paper_width', 80),
            'is_admin': printer_data.get('is_admin', False),
            'product_ids': printer_data.get('product_ids', []),
            'product_names': printer_data.get('product_names', {}),
        }
        if HAS_REQ:
            r = _req.post(full, json=payload, headers=_NGROK_HEADER, timeout=15, verify=False)
            try: data = r.json()
            except: return False, None, f"Server xatosi ({r.status_code}): {r.text[:100]}"
        else:
            body = json.dumps(payload).encode()
            req = urllib.request.Request(full, data=body, method='POST')
            req.add_header('Content-Type', 'application/json')
            req.add_header('ngrok-skip-browser-warning', 'true')
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = json.loads(resp.read())
        if data.get('success'):
            return True, data.get('printer_id'), None
        return False, None, data.get('error', 'Sync xato')
    except Exception as e:
        logger.error(f"Printer sync xato: {e}")
        return False, None, str(e)


def api_agent_auth(server_url, username, password):
    """POST /api/v2/agent/auth/ → (ok, business_id, business_name, error)"""
    try:
        full = f"{server_url}/api/v2/agent/auth/"
        if HAS_REQ:
            r = _req.post(full, json={'username': username, 'password': password},
                          headers=_NGROK_HEADER, timeout=10, verify=False)
            text = r.text.strip()
            if not text:
                return False, None, None, "Server bo'sh javob qaytardi (server ishlamayapti?)"
            try: data = r.json()
            except Exception: return False, None, None, f"Server xatosi ({r.status_code}): {text[:80]}"
        else:
            body = json.dumps({'username': username, 'password': password}).encode()
            req = urllib.request.Request(full, data=body, method='POST')
            req.add_header('Content-Type', 'application/json')
            req.add_header('ngrok-skip-browser-warning', 'true')
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                raw = resp.read()
                if not raw.strip(): return False, None, None, "Server bo'sh javob qaytardi"
                data = json.loads(raw)
        if data.get('success'):
            return True, str(data['business_id']), data.get('business_name', ''), None
        return False, None, None, data.get('error', 'Login yoki parol noto\'g\'ri')
    except Exception as e:
        return False, None, None, str(e)

def load_printers(business_id=None):
    """Business ID bo'yicha printerlarni yuklaydi. Eski formatdan migration ham qiladi."""
    pf = _printers_path(business_id)
    if pf.exists():
        try:
            with open(pf, encoding='utf-8') as f: return json.load(f)
        except: pass
    # Migration: eski printers.json mavjud bo'lsa, yangi formatga ko'chirish
    if business_id and PRINTERS_FILE.exists():
        try:
            with open(PRINTERS_FILE, encoding='utf-8') as f:
                old_data = json.load(f)
            if old_data:
                save_printers(old_data, business_id)
                return old_data
        except: pass
    return []

def save_printers(ps, business_id=None):
    pf = _printers_path(business_id)
    with open(pf, 'w', encoding='utf-8') as f:
        json.dump(ps, f, ensure_ascii=False, indent=2)

# ── WINDOWS AUTOSTART (registry) ─────────────────────────────
REG_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "NonborPrintAgent"

def get_autostart():
    if not IS_WIN or not HAS_REG: return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            winreg.QueryValueEx(k, REG_NAME)
            return True
    except: return False

def set_autostart(enable):
    if not IS_WIN or not HAS_REG: return
    exe = sys.executable if getattr(sys, 'frozen', False) else str(BASE_DIR / 'agent_app.py')
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enable:
                cmd = f'"{exe}" --minimized' if getattr(sys, 'frozen', False) \
                      else f'pythonw "{exe}" --minimized'
                winreg.SetValueEx(k, REG_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try: winreg.DeleteValue(k, REG_NAME)
                except: pass
    except Exception as e:
        logger.error(f"Registry xato: {e}")

# ── HTTP ─────────────────────────────────────────────────────
def _get(url, u, p, path, params=None):
    full = f"{url.rstrip('/')}/api/v2/{path}"
    if params: full += '?' + '&'.join(f'{k}={v}' for k,v in params.items())
    if HAS_REQ:
        return _req.get(full, auth=(u, p), headers=_NGROK_HEADER, timeout=10, verify=False).json()
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(full)
    req.add_header('Authorization', 'Basic ' + base64.b64encode(f'{u}:{p}'.encode()).decode())
    req.add_header('ngrok-skip-browser-warning', 'true')
    with urllib.request.urlopen(req, timeout=10, context=ctx) as r: return json.loads(r.read())

def _post(url, u, p, path, data):
    full = f"{url.rstrip('/')}/api/v2/{path}"
    if HAS_REQ:
        return _req.post(full, json=data, auth=(u, p), headers=_NGROK_HEADER, timeout=10, verify=False).json()
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    body = json.dumps(data).encode()
    req = urllib.request.Request(full, data=body, method='POST')
    req.add_header('Authorization', 'Basic ' + base64.b64encode(f'{u}:{p}'.encode()).decode())
    req.add_header('Content-Type', 'application/json')
    req.add_header('ngrok-skip-browser-warning', 'true')
    with urllib.request.urlopen(req, timeout=10, context=ctx) as r: return json.loads(r.read())

# ── PRINTER ──────────────────────────────────────────────────
def local_printers():
    if IS_WIN and HAS_WIN32:
        try:
            raw = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
            return [n for _,_,n,_ in raw]
        except: pass
    return []

DRIVERS_DIR = BASE_DIR / 'drivers'

def get_available_usb_ports():
    """Windows USB Monitor portlarini olish (USB001, USB002, ...)"""
    if not IS_WIN:
        return []
    ports = []
    try:
        import subprocess as sp
        r = sp.run(['reg', 'query',
                     r'HKLM\SYSTEM\CurrentControlSet\Control\Print\Monitors\USB Monitor\Ports'],
                    capture_output=True, text=True, timeout=10)
        for line in r.stdout.split('\n'):
            line = line.strip()
            if line.startswith('USB'):
                ports.append(line.split()[0])
    except:
        pass
    if not ports:
        ports = [f"USB{i:03d}" for i in range(1, 5)]
    return ports

def install_bundled_drivers():
    """drivers/ papkadan .inf fayllarni Windows drayver do'koniga qo'shish.
    Returns: (installed_count, errors_list)
    """
    if not IS_WIN or not DRIVERS_DIR.exists():
        return 0, ["drivers/ papka topilmadi"]
    import subprocess as sp
    inf_files = list(DRIVERS_DIR.glob('**/*.inf'))
    if not inf_files:
        return 0, ["drivers/ papkada .inf fayl topilmadi"]
    installed = 0
    errors = []
    for inf in inf_files:
        try:
            r = sp.run(['pnputil', '/add-driver', str(inf), '/install'],
                        capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                installed += 1
                logger.info(f"Drayver o'rnatildi: {inf.name}")
            else:
                out = (r.stdout + r.stderr).strip()
                # Allaqachon mavjud — xatolik emas
                if 'already exists' in out.lower() or 'уже' in out.lower():
                    installed += 1
                else:
                    errors.append(f"{inf.name}: {out[:100]}")
        except Exception as e:
            errors.append(f"{inf.name}: {e}")
    return installed, errors

def install_printer_with_driver(port_name, printer_name, driver_name="Generic / Text Only"):
    """Printer qo'shish (drayver nomi bilan).
    Returns: (success, error_message)
    """
    if not IS_WIN:
        return False, "Faqat Windows da ishlaydi"
    import subprocess as sp
    try:
        cmd = (f'rundll32 printui.dll,PrintUIEntry /if '
               f'/b "{printer_name}" /r "{port_name}" /m "{driver_name}"')
        r = sp.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            logger.info(f"Printer o'rnatildi: {printer_name} ({port_name}) [{driver_name}]")
            return True, None
        return False, (r.stdout + r.stderr).strip()[:200]
    except Exception as e:
        return False, str(e)

def get_installed_printer_drivers():
    """Windows da o'rnatilgan printer drayverlar ro'yxati"""
    drivers = []
    try:
        import subprocess as sp
        r = sp.run(['powershell', '-Command',
                     'Get-PrinterDriver | Select-Object -ExpandProperty Name'],
                    capture_output=True, text=True, timeout=15)
        for line in r.stdout.strip().split('\n'):
            name = line.strip()
            if name:
                drivers.append(name)
    except:
        drivers = ['Generic / Text Only']
    return drivers

def detect_and_install_printers():
    """To'liq jarayon: drayver o'rnatish → printer qo'shish.
    Returns: (installed_printers, messages)
    """
    messages = []
    installed_printers = []

    # 1. Avval mavjud printerlarni tekshirish
    existing = local_printers()
    if existing:
        messages.append(f"✓ {len(existing)} ta printer allaqachon mavjud: {', '.join(existing)}")
        return installed_printers, messages

    # 2. drivers/ papkadan drayverlarni o'rnatish
    if DRIVERS_DIR.exists() and list(DRIVERS_DIR.glob('**/*.inf')):
        messages.append("📦 Drayverlar o'rnatilmoqda...")
        cnt, errs = install_bundled_drivers()
        if cnt:
            messages.append(f"✓ {cnt} ta drayver o'rnatildi")
        for e in errs:
            messages.append(f"⚠ {e}")

        # Drayver o'rnatilgandan keyin Windows avtomatik printerni tanishi kerak
        import time
        time.sleep(3)

        # Yangi printerlarni tekshirish
        new_printers = local_printers()
        if new_printers:
            messages.append(f"✓ Printerlar topildi: {', '.join(new_printers)}")
            return installed_printers, messages

    # 3. USB portlarni tekshirish va Generic drayver bilan o'rnatish
    usb_ports = get_available_usb_ports()
    messages.append(f"🔍 USB portlar: {', '.join(usb_ports) if usb_ports else 'topilmadi'}")

    # Mavjud drayverlar ro'yxati
    drivers = get_installed_printer_drivers()
    # POS/Thermal/XPrinter drayverini afzal ko'rish
    pos_driver = 'Generic / Text Only'
    for d in drivers:
        dl = d.lower()
        if any(k in dl for k in ['xprinter', 'pos-', 'pos ', 'thermal', 'receipt', 'gprinter']):
            pos_driver = d
            break

    messages.append(f"🖨 Drayver: {pos_driver}")

    for port in usb_ports:
        name = f"POS-Printer ({port})"
        ok, err = install_printer_with_driver(port, name, pos_driver)
        if ok:
            installed_printers.append(name)
            messages.append(f"✓ {name} o'rnatildi")
        else:
            messages.append(f"⚠ {port}: {err}")

    # 4. Yana tekshirish
    final = local_printers()
    if final and not installed_printers:
        messages.append(f"✓ Printerlar: {', '.join(final)}")

    if not final and not installed_printers:
        messages.append("\n❌ Printer o'rnatib bo'lmadi.\n"
                        "Printer drayveri topilmadi.\n\n"
                        "Drayver yuklab olish:\n"
                        "  https://www.xprintertech.com/all-products/thermal-receipt-printer-driver-download\n\n"
                        "Printeringiz modelini tanlang va drayverni o'rnating.")

    return installed_printers, messages

_I=b'\x1b\x40'; _CUT=b'\x1d\x56\x00'; _FEED=b'\x1b\x64\x03'
_BON=b'\x1b\x45\x01'; _BOFF=b'\x1b\x45\x00'; _LFT=b'\x1b\x61\x00'

def escpos(text, w=80):
    cw = 42 if w==80 else 32
    out = bytearray(_I)
    for line in text.split('\n'):
        b = any(x in line for x in ['JAMI:','Buyurtma:','Tel:','====','! IZOH','Manzil:'])
        out += _LFT
        if '====' in line: out += ('='*cw).encode()
        elif '----' in line: out += ('-'*cw).encode()
        else:
            if b: out += _BON
            out += line.encode('utf-8', errors='replace')
            if b: out += _BOFF
        out += b'\n'
    return bytes(out + _FEED + _CUT)

def print_net(ip, port, data):
    try:
        s = socket.socket(); s.settimeout(5)
        s.connect((ip, int(port))); s.sendall(data); s.close()
        return True, None
    except Exception as e: return False, str(e)

def print_usb(name, data):
    if not HAS_WIN32: return False, "pywin32 kerak"
    if not name or not name.strip():
        return False, "Windows printer nomi kiritilmagan"
    # Tekshirish — printer mavjudmi
    known = local_printers()
    if known and name not in known:
        return False, f"'{name}' nomli printer topilmadi.\nMavjud printerlar: {', '.join(known)}"
    try:
        h = win32print.OpenPrinter(name)
        try:
            win32print.StartDocPrinter(h,1,("Nonbor",None,"RAW"))
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, data)
            win32print.EndPagePrinter(h)
            win32print.EndDocPrinter(h)
            return True, None
        finally: win32print.ClosePrinter(h)
    except Exception as e: return False, f"Printer xato: {e}"

def do_print(p_cfg, content):
    conn  = p_cfg.get('connection','auto')
    ip    = p_cfg.get('ip','')
    port  = p_cfg.get('port', 9100)
    usb   = p_cfg.get('usb','')
    width = int(p_cfg.get('paper_width', 80))
    data  = escpos(content, width)
    # Tarmoq yoki WiFi — TCP/IP orqali
    if conn in ('network', 'wifi'):
        if not ip: return False, "IP manzil kiritilmagan"
        return print_net(ip, port, data)
    # USB — Windows printer driver orqali
    if conn == 'usb':
        if not usb: return False, "USB printer tanlanmagan"
        return print_usb(usb, data) if IS_WIN else (False, "USB faqat Windows da ishlaydi")
    # Cloud/Auto — avval USB, keyin default printer
    if conn == 'auto':
        if usb:
            return print_usb(usb, data) if IS_WIN else (False, "USB faqat Windows da ishlaydi")
        # Default Windows printer ga yuborish
        if IS_WIN and HAS_WIN32:
            try:
                dp = win32print.GetDefaultPrinter()
                if dp:
                    return print_usb(dp, data)
            except Exception:
                pass
        return False, "Cloud rejimda chop etish uchun default printer topilmadi"
    return False, "Noto'g'ri ulanish turi"

# ── AGENT CORE ───────────────────────────────────────────────
class Agent:
    def __init__(self):
        self.running = False
        self.server_url = SERVER_URL
        self.business_id = ''
        self.business_name = ''
        self.username = ''
        self.password = ''
        self.poll_interval = 5
        self.printers = []
        self.printed = 0
        self.errors  = 0
        self._cbs = []
        self._thread = None
        self.reload()

    def reload(self):
        c = load_config()
        saved_url = _cfg_get(c,'settings','server_url','')
        self.server_url    = saved_url if saved_url else SERVER_URL
        self.business_id   = _cfg_get(c,'business','id','')
        self.business_name = _cfg_get(c,'business','name','')
        self.username      = _cfg_get(c,'auth','username','')
        self.password      = _cfg_get(c,'auth','password','')
        self.poll_interval = int(_cfg_get(c,'settings','poll_interval','5'))
        self.printers      = load_printers(self.business_id)

    def log(self, msg, lvl='info'):
        ts = datetime.now().strftime('%H:%M:%S')
        line = f"[{ts}] {msg}"
        getattr(logger, lvl if lvl in ('info','error','warning') else 'info')(msg)
        for cb in self._cbs:
            try: cb(line, lvl)
            except: pass

    def _find_printer(self, job):
        name = (job.get('printer_name') or '').strip().lower()
        return next((p for p in self.printers if p.get('name','').lower()==name), None)

    def _poll_orders(self):
        """Nonbor API dan barcha bizneslarning buyurtmalarini tekshirish (server orqali).
        /poll-all/ endpointi barcha aktiv+printerli bizneslarni bir vaqtda poll qiladi."""
        try:
            r = _post(self.server_url, self.username, self.password,
                      'nonbor/poll-all/', {})
            total_new = r.get('total_new', 0)
            total_printed = r.get('total_printed', 0)
            results = r.get('results', [])
            if total_new > 0:
                for res in results:
                    bname = res.get('business_name', '?')
                    bnew = res.get('new_orders', 0)
                    bprinted = res.get('printed', 0)
                    if bnew > 0:
                        self.log(f"📦 {bname}: {bnew} ta yangi buyurtma, {bprinted} ta chop etildi")
        except Exception:
            # Fallback: eski usul — faqat o'z biznesini poll qilish
            try:
                r = _post(self.server_url, self.username, self.password,
                          f'nonbor/poll/{self.business_id}/', {})
                new = r.get('new_orders', 0)
                if new > 0:
                    self.log(f"Nonbor: {new} ta yangi buyurtma")
            except Exception:
                pass

    def _poll(self):
        # 1) Nonbor API dan barcha bizneslarning buyurtmalarini tekshir
        self._poll_orders()

        # 2) Pending print joblarni ol (barcha bizneslar uchun)
        try:
            r = _get(self.server_url, self.username, self.password,
                     'print-job/agent/poll/', {'business_id': 'all'})
        except Exception as e:
            self.log(f"Server: {e}", 'error'); return

        jobs = r.get('result', []) if r.get('success') else []
        if not jobs: return
        self.log(f"{len(jobs)} ta yangi buyurtma!")

        for job in jobs:
            jid  = job['id']
            oid  = job['order_id']
            pnm  = job.get('printer_name','?')
            p    = self._find_printer(job)

            if p and p.get('connection') != 'auto':
                ok, err = do_print(p, job.get('content',''))
            else:
                cfg = {'connection': job.get('printer_connection','cloud'),
                       'ip':         job.get('printer_ip',''),
                       'port':       job.get('printer_port',9100),
                       'usb':        job.get('printer_usb',''),
                       'paper_width':job.get('paper_width',80)}
                ok, err = do_print(cfg, job.get('content',''))

            try:
                _post(self.server_url, self.username, self.password,
                      'print-job/agent/complete/',
                      {'job_id':jid,'status':'completed' if ok else 'failed','error':err or ''})
            except Exception as e:
                self.log(f"Javob xato: {e}", 'error')

            if ok:
                self.printed += 1
                self.log(f"  ✓ #{oid} [{pnm}]")
            else:
                self.errors += 1
                self.log(f"  ✗ #{oid} [{pnm}] {err}", 'error')

    def _loop(self):
        while self.running:
            try: self._poll()
            except Exception as e: self.log(f"Xato: {e}",'error')
            time.sleep(self.poll_interval)

    def start(self):
        if self.running: return
        self.reload()
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.log(f"Agent ishga tushdi. {len(self.printers)} ta printer.")

    def stop(self):
        self.running = False
        self.log("Agent to'xtatildi.")

    def test(self):
        try:
            r = _get(self.server_url, self.username, self.password,
                     'printer/list/', {'business_id': self.business_id})
            ps = r.get('result', [])
            return True, f"OK! Serverda {len(ps)} ta printer."
        except Exception as e:
            return False, str(e)

# ── TRAY ICON ────────────────────────────────────────────────
def make_tray_image(active=False):
    img  = Image.new('RGBA', (64, 64), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    c    = (79, 70, 229) if active else (220, 38, 38)
    # Printer body
    draw.rounded_rectangle([8,20,56,46], radius=4, fill=c)
    # Paper tray (top)
    draw.rounded_rectangle([18,10,46,24], radius=3, fill=c)
    # Paper output
    draw.rectangle([20,38,44,58], fill='white')
    draw.rectangle([24,44,40,48], fill=c)
    # Status dot
    dot = (22,163,74) if active else (220,38,38)
    draw.ellipse([42,24,54,36], fill=dot, outline='white', width=1)
    return img

# ── PRINTER DIALOG ───────────────────────────────────────────
class PrinterDlg(tk.Toplevel):
    def __init__(self, parent, local_ps, data=None, credentials=None, all_printers=None):
        """
        credentials = (server_url, username, password, business_id)
        all_printers = barcha saqlangan printerlar ro'yxati (mahsulot biriktirishni ko'rsatish uchun)
        """
        super().__init__(parent)
        self.result        = None
        self._lps          = local_ps
        self._creds        = credentials  # (server_url, username, password, business_id)
        self._products     = []           # [{id, name, category_name}]
        self._checkvars    = {}           # product_id → BooleanVar
        self._all_printers = all_printers or []
        self._current_pid  = (data or {}).get('id')  # tahrirlash rejimida joriy printer ID
        self._prod_loading = False
        self.title("Printer" + (" tahrirlash" if data else " qo'shish"))
        self.configure(bg='#f0f4f8')
        self.resizable(True, True)

        # Ekran o'lchamiga moslash
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = min(520, sw - 60)
        h  = min(700, sh - 80)
        x  = (sw - w) // 2
        y  = max(20, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(400, 480)

        self.transient(parent); self.grab_set()
        self._build(data or {})
        self._sync()
        # Products ni background da yuklash
        if credentials:
            threading.Thread(target=self._load_products,
                             args=(data or {},), daemon=True).start()

    def _lbl(self, parent, text):
        return tk.Label(parent, text=text, width=16, anchor='w',
                        font=('Segoe UI',10), fg='#475569', bg='#ffffff')

    def _entry(self, parent, val=''):
        e = tk.Entry(parent, font=('Segoe UI',10), bg='#f8fafc', fg='#1e293b',
                     insertbackground='#1e293b', relief='solid', bd=1)
        e.insert(0, val); return e

    def _build(self, d):
        fp = dict(padx=16, pady=4)

        # ══ YUQORI QISM: har doim ko'rinadigan maydonlar (fixed) ════════
        top = tk.Frame(self, bg='#ffffff')
        top.pack(side='top', fill='x')

        # Topilgan printerlar (har doim ko'rinadi)
        dp = tk.Frame(top, bg='#eef2ff', padx=12, pady=6)
        dp.pack(fill='x')
        dh = tk.Frame(dp, bg='#eef2ff'); dh.pack(fill='x')
        tk.Label(dh, text="🔍 Topilgan printerlar",
                 font=('Segoe UI',9,'bold'), fg='#4f46e5', bg='#eef2ff').pack(side='left')
        tk.Button(dh, text="🔄", command=self._refresh_detected,
                  bg='#e0e7ff', fg='#4f46e5', relief='flat',
                  font=('Segoe UI',8), cursor='hand2', padx=6, pady=1).pack(side='right')
        self._det_frame = tk.Frame(dp, bg='#eef2ff')
        self._det_frame.pack(fill='x', pady=(4,0))
        self._populate_detected()

        # Printer nomi (display name) — masalan: "Oshxona", "Osh", "Somsa"
        rl = tk.Frame(top, bg='#ffffff'); rl.pack(fill='x', **fp)
        self._lbl(rl, "Printer nomi *").pack(side='left')
        self._label = self._entry(rl, d.get('label', ''))
        self._label.pack(side='left', fill='x', expand=True)
        tk.Label(top, text="  Masalan: Oshxona printer, Bar printer, Ichimlik",
                 font=('Segoe UI',8), fg='#4f46e5', bg='#ffffff').pack(anchor='w', padx=16)

        # Server nomi
        r = tk.Frame(top, bg='#ffffff'); r.pack(fill='x', **fp)
        self._lbl(r, "Server nomi *").pack(side='left')
        self._name = self._entry(r, d.get('name', ''))
        self._name.pack(side='left', fill='x', expand=True)
        tk.Label(top, text="  Nonbor paneldagi printer nomiga aynan mos bo'lsin",
                 font=('Segoe UI',8), fg='#94a3b8', bg='#ffffff').pack(anchor='w', padx=16)

        # Ulanish turi
        r2 = tk.Frame(top, bg='#ffffff'); r2.pack(fill='x', **fp)
        self._lbl(r2, "Ulanish turi *").pack(side='left')
        self._conn = tk.StringVar(value=d.get('connection', 'network'))
        for v, t in [('network','🌐 Tarmoq (LAN)'), ('wifi','📶 WiFi'), ('usb','🖨 USB'), ('auto','☁ Cloud')]:
            tk.Radiobutton(r2, text=t, variable=self._conn, value=v,
                           bg='#ffffff', fg='#1e293b', selectcolor='#eef2ff',
                           activebackground='#ffffff', font=('Segoe UI',9),
                           command=self._sync).pack(side='left', padx=4)

        # Ulanish tushuntirmasi
        self._conn_hint = tk.Label(top, text="", font=('Segoe UI',8),
                                    fg='#4f46e5', bg='#ffffff', anchor='w', wraplength=440)
        self._conn_hint.pack(fill='x', padx=16)

        # ── Ulanish sozlamalari konteyneri (pack tartibini saqlash) ──
        self._conn_box = tk.Frame(top, bg='#ffffff')
        self._conn_box.pack(fill='x')

        # ── Tarmoq/WiFi maydonlari (IP + Port) ──
        self._nf = tk.Frame(self._conn_box, bg='#ffffff')
        self._nf.pack(fill='x', padx=16)
        rn = tk.Frame(self._nf, bg='#ffffff'); rn.pack(fill='x', pady=2)
        self._lbl(rn, "IP manzil *").pack(side='left')
        self._ip   = self._entry(rn, d.get('ip', ''))
        self._ip.pack(side='left', fill='x', expand=True)
        self._lbl(rn, "  Port").pack(side='left')
        self._port = self._entry(rn, str(d.get('port', 9100)))
        self._port.config(width=7); self._port.pack(side='left')

        # ── USB maydonlari (Windows printer tanlash) ──
        self._uf = tk.Frame(self._conn_box, bg='#ffffff')
        self._uf.pack(fill='x', padx=16)
        ru = tk.Frame(self._uf, bg='#ffffff'); ru.pack(fill='x', pady=2)
        self._lbl(ru, "Windows printer *").pack(side='left')
        self._usb = tk.StringVar(value=d.get('usb', ''))
        self._cb  = ttk.Combobox(ru, textvariable=self._usb, font=('Segoe UI',10),
                                  state='readonly')
        self._cb['values'] = self._lps
        self._cb.pack(side='left', fill='x', expand=True)
        # USB da eskidan noto'g'ri nom bo'lsa, ro'yxatdan qayta tanlash kerak
        if d.get('usb','') and d.get('usb','') not in self._lps:
            self._usb.set('')

        # ── Cloud tushuntirish paneli ──
        self._cf = tk.Frame(self._conn_box, bg='#eef2ff', padx=12, pady=8)
        self._cf.pack(fill='x', padx=16, pady=(2,0))
        tk.Label(self._cf, text="☁  Cloud rejimda printer serverdan boshqariladi.\n"
                 "Agent buyurtmani serverdan oladi va shu kompyuterga\n"
                 "ulangan printerga chop etadi. IP/USB kiritish shart emas.",
                 font=('Segoe UI',8), fg='#4f46e5', bg='#eef2ff',
                 anchor='w', justify='left').pack(anchor='w')

        # Qog'oz kengligi
        rw = tk.Frame(top, bg='#ffffff'); rw.pack(fill='x', **fp)
        self._lbl(rw, "Qog'oz kengligi").pack(side='left')
        self._pw = tk.StringVar(value=str(d.get('paper_width', 80)))
        for v, t in [('80','80 mm'), ('58','58 mm')]:
            tk.Radiobutton(rw, text=t, variable=self._pw, value=v,
                           bg='#ffffff', fg='#1e293b', selectcolor='#eef2ff',
                           activebackground='#ffffff', font=('Segoe UI',9)).pack(side='left', padx=8)

        # Admin printer checkbox
        ra = tk.Frame(top, bg='#ffffff'); ra.pack(fill='x', **fp)
        self._is_admin = tk.BooleanVar(value=d.get('is_admin', False))
        tk.Checkbutton(ra, text="  Admin printer (barcha buyurtmalarni ko'rsatadi)",
                       variable=self._is_admin, bg='#ffffff', fg='#1e293b',
                       selectcolor='#eef2ff', activebackground='#ffffff',
                       font=('Segoe UI',9,'bold')).pack(side='left')

        # ══ PASTKI QISM: Saqlash/Bekor — side='bottom', har doim ko'rinadi ══
        bf = tk.Frame(self, bg='#e2e8f0'); bf.pack(side='bottom', fill='x', padx=0, pady=0)
        tk.Frame(bf, bg='#cbd5e1', height=1).pack(fill='x')
        btn_row = tk.Frame(bf, bg='#e2e8f0'); btn_row.pack(fill='x', padx=16, pady=8)
        tk.Button(btn_row, text="✓  Saqlash", command=self._ok,
                  bg='#4f46e5', fg='white', font=('Segoe UI',10,'bold'),
                  relief='flat', padx=20, pady=7, cursor='hand2',
                  activebackground='#4338ca', activeforeground='white').pack(side='right', padx=(8,0))
        tk.Button(btn_row, text="Bekor", command=self.destroy,
                  bg='#94a3b8', fg='white', font=('Segoe UI',10),
                  relief='flat', padx=16, pady=7, cursor='hand2').pack(side='right')

        # ══ O'RTA QISM: Mahsulotlar — qolgan joyni to'ldiradi, scroll bilan ════
        tk.Frame(self, bg='#cbd5e1', height=1).pack(fill='x')
        mh = tk.Frame(self, bg='#ffffff', padx=16, pady=4)
        mh.pack(fill='x')
        tk.Label(mh, text="🍽  Mahsulotlar",
                 font=('Segoe UI',9,'bold'), fg='#1e293b', bg='#ffffff').pack(side='left')
        self._prod_count_lbl = tk.Label(mh, text="",
                 font=('Segoe UI',8), fg='#64748b', bg='#ffffff')
        self._prod_count_lbl.pack(side='left', padx=4)
        abf = tk.Frame(mh, bg='#ffffff'); abf.pack(side='right')
        tk.Button(abf, text="☑ Barchasi", command=self._check_all,
                  bg='#e0e7ff', fg='#4f46e5', relief='flat',
                  font=('Segoe UI',8), cursor='hand2', padx=6, pady=1).pack(side='left', padx=2)
        tk.Button(abf, text="☐ Hech biri", command=self._uncheck_all,
                  bg='#e0e7ff', fg='#4f46e5', relief='flat',
                  font=('Segoe UI',8), cursor='hand2', padx=6, pady=1).pack(side='left')

        # Scrollable products container — fill='both', expand=True (qolgan joy)
        pc = tk.Frame(self, bg='#fafbfc')
        pc.pack(fill='both', expand=True, padx=0, pady=0)

        self._prod_canvas = tk.Canvas(pc, bg='#fafbfc', highlightthickness=0)
        vsb = ttk.Scrollbar(pc, orient='vertical', command=self._prod_canvas.yview)
        self._prod_sf = tk.Frame(self._prod_canvas, bg='#fafbfc')
        self._prod_sf.bind('<Configure>', lambda e: self._prod_canvas.configure(
            scrollregion=self._prod_canvas.bbox('all')))
        self._prod_win = self._prod_canvas.create_window((0, 0), window=self._prod_sf, anchor='nw')
        self._prod_canvas.configure(yscrollcommand=vsb.set)
        self._prod_canvas.bind('<Configure>',
            lambda e: self._prod_canvas.itemconfigure(self._prod_win, width=e.width))
        # MouseWheel scroll (faqat products canvas ustida)
        self._prod_canvas.bind('<Enter>',
            lambda e: self._prod_canvas.bind_all('<MouseWheel>', self._on_scroll))
        self._prod_canvas.bind('<Leave>',
            lambda e: self._prod_canvas.unbind_all('<MouseWheel>'))
        vsb.pack(side='right', fill='y')
        self._prod_canvas.pack(side='left', fill='both', expand=True)

        # Loading status
        self._prod_status = tk.Label(self._prod_sf,
            text="⏳ Mahsulotlar yuklanmoqda..." if self._creds else
                 "ℹ  Tizimga kirish kerak",
            font=('Segoe UI',9), fg='#64748b', bg='#fafbfc', anchor='w')
        self._prod_status.pack(fill='x', padx=12, pady=10)

    def _on_scroll(self, event):
        self._prod_canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')

    def _populate_detected(self):
        for w in self._det_frame.winfo_children():
            w.destroy()
        if not self._lps:
            tk.Label(self._det_frame, text="  Printer topilmadi",
                     font=('Segoe UI',8), fg='#94a3b8', bg='#eef2ff').pack(anchor='w')
            return
        # Max 3 ta ko'rinadigan, scroll bilan
        det_canvas = tk.Canvas(self._det_frame, bg='#eef2ff',
                                highlightthickness=0,
                                height=min(len(self._lps), 3) * 26)
        det_vsb = ttk.Scrollbar(self._det_frame, orient='vertical',
                                  command=det_canvas.yview)
        det_inner = tk.Frame(det_canvas, bg='#eef2ff')
        det_inner.bind('<Configure>', lambda e: det_canvas.configure(
            scrollregion=det_canvas.bbox('all')))
        det_win = det_canvas.create_window((0, 0), window=det_inner, anchor='nw')
        det_canvas.configure(yscrollcommand=det_vsb.set)
        det_canvas.bind('<Configure>',
            lambda e: det_canvas.itemconfigure(det_win, width=e.width))
        if len(self._lps) > 3:
            det_vsb.pack(side='right', fill='y')
        det_canvas.pack(side='left', fill='x', expand=True)
        for pname in self._lps:
            btn = tk.Button(det_inner, text=f"🖨  {pname}",
                            command=lambda n=pname: self._select_detected(n),
                            bg='#e0e7ff', fg='#1e293b', relief='flat',
                            font=('Segoe UI',9), anchor='w', cursor='hand2',
                            padx=8, pady=3, bd=0)
            btn.pack(fill='x', pady=1)
            btn.bind('<Enter>', lambda e, b=btn: b.config(bg='#c7d2fe'))
            btn.bind('<Leave>', lambda e, b=btn: b.config(bg='#e0e7ff'))

    def _refresh_detected(self):
        self._lps = local_printers()
        self._populate_detected()
        self._cb['values'] = self._lps

    def _select_detected(self, name):
        self._conn.set('usb')
        self._sync()
        self._usb.set(name)
        if not self._name.get().strip():
            self._name.delete(0, 'end')
            self._name.insert(0, name)
        if not self._label.get().strip():
            self._label.focus()

    # ── Mahsulotlar ───────────────────────────────────────────
    def _load_products(self, existing_data):
        """Background thread: mahsulotlarni serverdan yuklab, UI ni yangilaydi.
        Server ishlamasa — lokal keshdan yuklaydi."""
        su, uname, pwd, bid = self._creds
        bid_int = int(bid)
        cache_file = _cache_path(bid)
        ok, products, err = api_fetch_menu(su, uname, pwd, bid_int)

        if ok and products:
            # Keshga saqlash (business_id bo'yicha alohida)
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump({'bid': bid_int, 'products': products}, f, ensure_ascii=False)
            except Exception:
                pass
        elif not ok:
            # Server ishlamadi — keshdan yuklash
            try:
                # Avval yangi formatdagi kesh
                cf = cache_file if cache_file.exists() else PRODUCTS_CACHE
                if cf.exists():
                    with open(cf, encoding='utf-8') as f:
                        cached = json.load(f)
                    if cached.get('bid') == bid_int and cached.get('products'):
                        products = cached['products']
                        ok = True
                        err = None
            except Exception:
                pass

        self._products = products
        existing_ids = set(existing_data.get('product_ids', []))
        try:
            self.after(0, self._render_products, products, existing_ids, err)
        except Exception:
            pass

    def _render_products(self, products, existing_ids, err):
        """Main thread: products ni checkboxes sifatida ko'rsatish"""
        # Status labelni o'chirish
        if self._prod_status:
            self._prod_status.destroy()
            self._prod_status = None

        if err:
            self._prod_status = tk.Label(self._prod_sf, text=f"⚠  {err}",
                font=('Segoe UI',8), fg='#dc2626', bg='#fafbfc', anchor='w',
                wraplength=380, justify='left')
            self._prod_status.pack(fill='x', padx=8, pady=8)
            self._prod_count_lbl.config(text="— xato")
            return
        if not products:
            self._prod_status = tk.Label(self._prod_sf,
                text="ℹ  Nonbor menyuda mahsulotlar yo'q. Avval Nonbor panel da mahsulot qo'shing.",
                font=('Segoe UI',8), fg='#94a3b8', bg='#fafbfc', anchor='w',
                wraplength=380, justify='left')
            self._prod_status.pack(fill='x', padx=8, pady=8)
            self._prod_count_lbl.config(text="— 0 ta")
            return

        # Mahsulot → printer nomi mapping (barcha printerlar)
        prod_to_printers = {}
        for pr in self._all_printers:
            pr_name = pr.get('name', '?')
            is_current = pr.get('id') == self._current_pid
            for pid2 in pr.get('product_ids', []):
                label = f"{pr_name} ✎" if is_current else pr_name
                prod_to_printers.setdefault(pid2, []).append(label)

        # Kategoriya bo'yicha guruhlash
        cats = {}
        for p in products:
            cname = p.get('category_name') or 'Boshqa'
            if cname not in cats:
                cats[cname] = []
            cats[cname].append(p)

        self._checkvars = {}
        for cat_name, items in sorted(cats.items()):
            # Kategoriya header
            tk.Label(self._prod_sf, text=f"  {cat_name}",
                     font=('Segoe UI',9,'bold'), fg='#4f46e5', bg='#fafbfc',
                     anchor='w').pack(fill='x', padx=4, pady=(6,2))
            for p in items:
                pid = p.get('id')
                pname = p.get('name', '')
                var = tk.BooleanVar(value=(pid in existing_ids))
                self._checkvars[pid] = var
                row = tk.Frame(self._prod_sf, bg='#fafbfc')
                row.pack(fill='x', padx=4, pady=1)
                cb = tk.Checkbutton(row, variable=var,
                    text=f"  {pname}",
                    font=('Segoe UI',9), fg='#1e293b', bg='#fafbfc',
                    selectcolor='#eef2ff', activebackground='#fafbfc',
                    activeforeground='#1e293b',
                    anchor='w', command=self._update_count)
                cb.pack(side='left', fill='x', expand=True)
                # Qaysi printerga biriktirilgan
                assigned = prod_to_printers.get(pid, [])
                if assigned:
                    lbl_txt = "🖨 " + ",  ".join(assigned)
                    tk.Label(row, text=lbl_txt,
                             font=('Segoe UI', 8), fg='#4f46e5', bg='#fafbfc',
                             anchor='e').pack(side='right', padx=(0, 6))

        self._update_count()

    def _update_count(self):
        total = len(self._checkvars)
        selected = sum(1 for v in self._checkvars.values() if v.get())
        self._prod_count_lbl.config(
            text=f"— {selected}/{total} tanlangan",
            fg='#4f46e5' if selected else '#94a3b8')

    def _check_all(self):
        for v in self._checkvars.values(): v.set(True)
        self._update_count()

    def _uncheck_all(self):
        for v in self._checkvars.values(): v.set(False)
        self._update_count()

    def _sync(self):
        conn = self._conn.get()
        hints = {
            'network': '📡 Kabel orqali (Ethernet). Printer IP va portini kiriting.',
            'wifi':    '📶 WiFi orqali. Printer IP va portini kiriting (tarmoqdagidek).',
            'usb':     '🖨 USB kabel orqali ulangan. Windows printer nomini tanlang.',
            'auto':    '☁ Server orqali masofadan. Default printerga chop etiladi.',
        }
        self._conn_hint.config(text=hints.get(conn, ''))
        show_net = conn in ('network', 'wifi')
        show_usb = conn == 'usb'
        show_cloud = conn == 'auto'
        # Avval hammasini yashirish
        self._nf.pack_forget()
        self._uf.pack_forget()
        self._cf.pack_forget()
        # Kerakli maydonlarni ko'rsatish (tartib saqlanadi)
        if show_net:
            self._nf.pack(fill='x', padx=16)
        elif show_usb:
            self._uf.pack(fill='x', padx=16)
        elif show_cloud:
            self._cf.pack(fill='x', padx=16, pady=(2,0))

    def _ok(self):
        label = self._label.get().strip()
        name = self._name.get().strip()
        if not label:
            messagebox.showwarning("","Printer nomini kiriting! (masalan: Oshxona printer)",parent=self); return
        if not name:
            messagebox.showwarning("","Server nomini kiriting! (Nonbor paneldagi nom)",parent=self); return
        conn = self._conn.get()
        if conn in ('network','wifi') and not self._ip.get().strip():
            messagebox.showwarning("","IP manzilni kiriting!",parent=self); return
        if conn=='usb' and not self._usb.get().strip():
            messagebox.showwarning("","Windows printerni tanlang!",parent=self); return

        # Tanlangan mahsulotlar
        product_ids = [pid for pid, var in self._checkvars.items() if var.get()]
        product_names = {pid: p.get('name','') for p in self._products
                         for pid2, var in self._checkvars.items()
                         if pid2 == p.get('id') and var.get()
                         for pid in [pid2]}

        self.result = {
            'id':           str(uuid.uuid4()),
            'label':        label,
            'name':         name,
            'connection':   conn,
            'ip':           self._ip.get().strip(),
            'port':         int(self._port.get().strip() or 9100),
            'usb':          self._usb.get().strip(),
            'paper_width':  int(self._pw.get()),
            'is_admin':     self._is_admin.get(),
            'product_ids':  product_ids,
            'product_names': {str(p['id']): p['name']
                              for p in self._products
                              if p['id'] in product_ids},
        }
        self.destroy()

# ── SETTINGS WINDOW ──────────────────────────────────────────
# ── LIGHT THEME ──
BG='#f0f4f8'; BG2='#ffffff'; BG3='#e2e8f0'
ACCENT='#4f46e5'; RED='#dc2626'; GREEN='#16a34a'
PURPLE='#7c3aed'; ORANGE='#ea580c'
FG='#1e293b'; FGD='#64748b'
CARD='#ffffff'; BORDER='#cbd5e1'; HOVER='#eef2ff'

class SettingsWindow:
    def __init__(self, agent: Agent, on_close_cb=None):
        self.agent      = agent
        self._on_close  = on_close_cb
        self._printers  = load_printers(agent.business_id)
        self._main_frame = None
        self._login_frame = None

        self.win = tk.Tk()
        self.win.title("Nonbor Print Agent")
        self.win.resizable(False, False)
        self.win.configure(bg=BG)
        self.win.protocol('WM_DELETE_WINDOW', self._hide)

        agent._cbs.append(self._on_log)
        self._build()

    def _btn(self, p, t, bg, cmd, **kw):
        fg = kw.get('fg', 'white')
        return tk.Button(p, text=t, command=cmd, bg=bg, fg=fg,
                         font=kw.get('font',('Segoe UI',9)), relief='flat',
                         padx=kw.get('padx',12), pady=4, cursor='hand2',
                         activebackground=bg, activeforeground=fg)

    def _build(self):
        # ── Header (gradient-style)
        h = tk.Frame(self.win, bg='#4f46e5', pady=14)
        h.pack(fill='x')
        tk.Label(h, text="🖨  NONBOR PRINT AGENT",
                 font=('Segoe UI',15,'bold'), fg='white', bg='#4f46e5').pack()
        tk.Label(h, text="nonbor.uz  •  Chop etish agenti",
                 font=('Segoe UI',9), fg='#c7d2fe', bg='#4f46e5').pack()

        # ── Footer (always shown)
        ft = tk.Frame(self.win, bg=BG3, pady=7, padx=16)
        ft.pack(fill='x', side='bottom')
        tk.Frame(self.win, bg=BORDER, height=1).pack(fill='x', side='bottom')
        self._auto = tk.BooleanVar(value=get_autostart())
        ttk.Checkbutton(ft, text="Windows yonganda avtomatik ishga tushir",
                        variable=self._auto, command=self._toggle_auto).pack(side='left')
        self._btn(ft, "✕ Chiqish", '#94a3b8', self._quit, padx=10).pack(side='right')

        # ── Content area
        self._content = tk.Frame(self.win, bg=BG)
        self._content.pack(fill='both', expand=True)

        if is_logged_in():
            self._show_main()
        else:
            self._show_login()

    # ── LOGIN FRAME ───────────────────────────────────────────
    def _show_login(self):
        self.win.geometry("480x540")
        if self._main_frame:
            self._main_frame.pack_forget()
        if self._login_frame:
            self._login_frame.destroy()

        f = tk.Frame(self._content, bg=BG)
        f.pack(fill='both', expand=True)
        self._login_frame = f
        self._saved_logins = load_saved_logins()

        # Spacer top
        tk.Frame(f, bg=BG, height=16).pack()

        # Card frame
        card = tk.Frame(f, bg=CARD, padx=28, pady=20,
                        highlightbackground='#e2e8f0', highlightthickness=1)
        card.pack(padx=24, fill='x')

        # Title
        title_f = tk.Frame(card, bg=CARD); title_f.pack(fill='x', pady=(0,12))
        tk.Label(title_f, text="Tizimga kirish",
                 font=('Segoe UI',14,'bold'), fg='#1e293b', bg=CARD).pack(anchor='w')
        tk.Label(title_f, text="Admin berilgan login va parolni kiriting",
                 font=('Segoe UI',9), fg='#94a3b8', bg=CARD).pack(anchor='w')

        # Server URL
        tk.Label(card, text="Server manzili", font=('Segoe UI',9,'bold'), fg='#475569', bg=CARD,
                 anchor='w').pack(fill='x')
        self._l_url = tk.Entry(card, font=('Segoe UI',10), bg='#f8fafc', fg=FG,
                                insertbackground=FG, relief='solid', bd=1)
        self._l_url.insert(0, self.agent.server_url)
        self._l_url.pack(fill='x', pady=(3,10), ipady=3)

        # Login label + input
        tk.Label(card, text="Login", font=('Segoe UI',9,'bold'), fg='#475569', bg=CARD,
                 anchor='w').pack(fill='x')
        usernames = [l['username'] for l in self._saved_logins]
        self._l_user = ttk.Combobox(card, values=usernames,
                                     font=('Segoe UI',11), width=28)
        self._l_user.pack(fill='x', pady=(3,12), ipady=3)
        self._l_user.bind('<<ComboboxSelected>>', self._on_login_select)

        # Parol label + input
        tk.Label(card, text="Parol", font=('Segoe UI',9,'bold'), fg='#475569', bg=CARD,
                 anchor='w').pack(fill='x')
        pf = tk.Frame(card, bg=CARD); pf.pack(fill='x', pady=(3,8))
        self._pass_visible = False
        self._l_pass = tk.Entry(pf, font=('Segoe UI',11), bg='#f8fafc', fg=FG,
                                 insertbackground=FG, relief='solid', bd=1,
                                 show='●')
        self._l_pass.pack(side='left', fill='x', expand=True, ipady=4)
        self._l_eye = tk.Button(pf, text='👁', command=self._toggle_pass,
                                 bg='#f1f5f9', fg='#94a3b8', relief='flat',
                                 font=('Segoe UI',10), cursor='hand2', padx=8, bd=0)
        self._l_eye.pack(side='left', padx=(4,0))
        self._l_pass.bind('<Return>', lambda e: self._do_login())

        # Error label
        self._l_err = tk.Label(card, text='', font=('Segoe UI',9), fg=RED, bg=CARD)
        self._l_err.pack(fill='x')

        # ── KIRISH BUTTON (katta, yorqin)
        self._l_btn = tk.Button(card, text="➜  Kirish",
                                 command=self._do_login,
                                 bg='#4f46e5', fg='white',
                                 font=('Segoe UI',12,'bold'),
                                 relief='flat', pady=10, cursor='hand2',
                                 activebackground='#4338ca', activeforeground='white')
        self._l_btn.pack(fill='x', pady=(6,0), ipady=2)

        # Saved logins hint
        if self._saved_logins:
            tk.Label(f, text=f"💾  {len(self._saved_logins)} ta saqlangan login mavjud",
                     font=('Segoe UI',8), fg=FGD, bg=BG).pack(pady=(10,0))

        self._l_user.focus()

    def _on_login_select(self, event=None):
        """Saqlangan logindan tanlaganda faqat username to'ldiriladi"""
        self._l_pass.delete(0, 'end')
        self._l_pass.focus()

    def _toggle_pass(self):
        self._pass_visible = not self._pass_visible
        self._l_pass.config(show='' if self._pass_visible else '●')
        self._l_eye.config(fg=ACCENT if self._pass_visible else '#94a3b8', bg=CARD)

    def _do_login(self):
        u = self._l_user.get().strip()
        p = self._l_pass.get().strip()
        url = self._l_url.get().strip().rstrip('/')
        if not url:
            self._l_err.config(text="Server manzilini kiriting!")
            return
        if not u or not p:
            self._l_err.config(text="Login va parolni kiriting!")
            return
        self._l_btn.config(text="⏳  Tekshirilmoqda...", state='disabled', bg='#6366f1')
        self._l_err.config(text='')
        self.win.update()

        ok, bid, bname, err = api_agent_auth(url, u, p)
        self._l_btn.config(text="➜  Kirish", state='normal', bg='#4f46e5')
        if not ok:
            self._l_err.config(text=f"✗ {err}")
            return

        self.agent.server_url    = url
        self.agent.username      = u
        self.agent.password      = p
        self.agent.business_id   = bid
        self.agent.business_name = bname
        save_config(self.agent)
        save_login_to_history(u)
        self._printers = load_printers(bid)
        self.agent.printers = self._printers
        self._show_main()

    # ── MAIN FRAME ────────────────────────────────────────────
    def _show_main(self):
        self.win.geometry("720x640")
        if self._login_frame:
            self._login_frame.pack_forget()
        if self._main_frame:
            self._main_frame.destroy()

        f = tk.Frame(self._content, bg=BG)
        f.pack(fill='both', expand=True)
        self._main_frame = f

        # ── Status bar (card style)
        sb = tk.Frame(f, bg=CARD, pady=10, padx=16, highlightbackground=BORDER,
                      highlightthickness=1)
        sb.pack(fill='x', padx=12, pady=(10,0))
        self._dot   = tk.Label(sb, text="●", font=('Segoe UI',18), fg=RED, bg=CARD)
        self._dot.pack(side='left')
        info_f = tk.Frame(sb, bg=CARD); info_f.pack(side='left', padx=8)
        self._stlbl = tk.Label(info_f, text="To'xtatilgan",
                                font=('Segoe UI',11,'bold'), fg=FG, bg=CARD)
        self._stlbl.pack(anchor='w')
        biz = self.agent.business_name or f"Biznes #{self.agent.business_id}"
        self._bizlbl = tk.Label(info_f, text=f"👤 {self.agent.username}  •  {biz}",
                                 font=('Segoe UI',9), fg=FGD, bg=CARD)
        self._bizlbl.pack(anchor='w')
        self._stats = tk.Label(sb, text="", font=('Segoe UI',9,'bold'), fg=FGD, bg=CARD)
        self._stats.pack(side='right', padx=8)
        self._togbtn = tk.Button(sb, text="▶  ISHGA TUSHIR",
                                  command=self._toggle,
                                  bg=GREEN, fg='white',
                                  font=('Segoe UI',10,'bold'),
                                  relief='flat', padx=18, pady=5, cursor='hand2',
                                  activebackground='#15803d', activeforeground='white')
        self._togbtn.pack(side='right')

        # ── Action buttons row
        uf = tk.Frame(f, bg=BG, padx=12, pady=6); uf.pack(fill='x')
        self._btn(uf, "🔄  Mahsulotlarni yangilash", '#059669', self._check_new_products).pack(side='left')
        self._btn(uf, "❓ Yordam", '#6366f1', self._show_help).pack(side='right', padx=(0,8))
        self._btn(uf, "⟳  Hisobdan chiqish", '#94a3b8', self._do_logout).pack(side='right')

        # ── Printers section (card)
        pc = tk.Frame(f, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        pc.pack(fill='x', padx=12, pady=(0,4))
        ph = tk.Frame(pc, bg=CARD, padx=12, pady=8); ph.pack(fill='x')
        tk.Label(ph, text="🖨  Printerlar", font=('Segoe UI',10,'bold'), fg=FG, bg=CARD).pack(side='left')
        tk.Label(ph, text="— server nomi bilan mos bo'lsin",
                 font=('Segoe UI',8), fg=FGD, bg=CARD).pack(side='left', padx=6)
        ab = tk.Frame(ph, bg=CARD); ab.pack(side='right')
        for t,clr,fn in [("🔍 Avtomatik topish",'#0891b2',self._auto_detect_printers),
                         ("+ Qo'shish",GREEN,self._add),
                         ("✎",'#4f46e5',self._edit),("⚡ Test",ORANGE,self._tst),
                         ("✕",RED,self._del)]:
            self._btn(ab,t,clr,fn,padx=8 if len(t)<4 else 12).pack(side='left',padx=2)

        # Treeview
        tf = tk.Frame(pc, bg=CARD, padx=12, pady=0); tf.pack(fill='x', pady=(0,8))
        style = ttk.Style(); style.theme_use('default')
        style.configure('T.Treeview', background='white', foreground=FG,
                         fieldbackground='white', rowheight=26, font=('Segoe UI',9))
        style.configure('T.Treeview.Heading', background='#4f46e5', foreground='white',
                         font=('Segoe UI',9,'bold'), padding=4)
        style.map('T.Treeview', background=[('selected','#eef2ff')],
                  foreground=[('selected','#1e293b')])
        cols = ('label','name','admin','conn','addr','width','prods')
        self._tree = ttk.Treeview(tf, style='T.Treeview',
                                   columns=cols, show='headings', height=5)
        for col,(hd,w) in zip(cols,[("Yorliq",100),("Printer nomi",120),
                                     ("Turi",55),("Ulanish",65),("Manzil",130),
                                     ("Qog'oz",45),("Mahsulotlar",110)]):
            self._tree.heading(col, text=hd)
            self._tree.column(col, width=w, anchor='w')
        self._tree.pack(fill='x')
        self._tree.bind('<Double-1>', lambda e: self._edit())
        self._tree.bind('<<TreeviewSelect>>', self._on_tree_select)

        # Mahsulotlar detail panel
        self._prod_panel = tk.Frame(pc, bg='#f8fafc', padx=12, pady=6)
        self._prod_panel.pack(fill='x', padx=12, pady=(0,8))
        self._prod_detail = tk.Label(self._prod_panel,
            text="Printer tanlang — mahsulotlar ko'rinadi",
            font=('Segoe UI',8), fg=FGD, bg='#f8fafc', anchor='w',
            wraplength=640, justify='left')
        self._prod_detail.pack(fill='x')

        # ── Log (card)
        lc = tk.Frame(f, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        lc.pack(fill='both', expand=True, padx=12, pady=(0,8))
        lh = tk.Frame(lc, bg=CARD, padx=12, pady=4); lh.pack(fill='x')
        tk.Label(lh, text="📋  Faoliyat jurnali", font=('Segoe UI',9,'bold'),
                 fg=FG, bg=CARD).pack(anchor='w')
        self._log = scrolledtext.ScrolledText(
            lc, font=('Consolas',9), bg='#1e293b', fg='#a5b4fc',
            relief='flat', bd=0, state='disabled', height=6)
        self._log.tag_config('error', foreground='#fca5a5')
        self._log.tag_config('ok',    foreground='#86efac')
        self._log.pack(fill='both', expand=True, padx=8, pady=(0,8))

        self._refresh_tbl()
        self._tick()

    def _check_new_products(self):
        """Yangi mahsulotlar borligini tekshiradi — eski sozlamalar o'zgarmasdan."""
        su   = self.agent.server_url
        uname = self.agent.username
        pwd   = self.agent.password
        bid   = self.agent.business_id
        if not (su and uname and pwd and bid):
            messagebox.showwarning("Diqqat", "Avval tizimga kiring.", parent=self.win)
            return

        self._logline("🔄 Yangi mahsulotlar tekshirilmoqda...")

        def _run():
            cache_file = _cache_path(bid)
            ok, products, err = api_fetch_menu(su, uname, pwd, bid)
            if ok and products:
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump({'bid': int(bid), 'products': products}, f, ensure_ascii=False)
                except Exception:
                    pass
            elif not ok:
                # Keshdan yuklash
                try:
                    cf = cache_file if cache_file.exists() else PRODUCTS_CACHE
                    if cf.exists():
                        with open(cf, encoding='utf-8') as f:
                            cached = json.load(f)
                        if cached.get('bid') == int(bid) and cached.get('products'):
                            products = cached['products']
                            ok = True
                except Exception:
                    pass
            if not ok:
                self.win.after(0, lambda: messagebox.showerror(
                    "Xato", f"Serverdan ma'lumot olishda xato:\n{err}", parent=self.win))
                return

            # Barcha mavjud product_ids (barcha printerlardan)
            all_assigned = set()
            for p in self._printers:
                for pid in p.get('product_ids', []):
                    all_assigned.add(int(pid))

            # Yangi mahsulotlar — hech bir printerga biriktirilmagan
            new_products = [p for p in products if int(p['id']) not in all_assigned]

            if not new_products:
                self.win.after(0, lambda: (
                    self._logline("✓ Yangilik yo'q — barcha mahsulotlar allaqachon ro'yxatda."),
                    messagebox.showinfo(
                        "Yangilik yo'q",
                        "✓ Yangi mahsulot topilmadi.\nBarcha mahsulotlar printerlar ro'yxatida mavjud.",
                        parent=self.win)
                ))
                return

            # Yangi mahsulotlar bor — dialog ko'rsatish
            self.win.after(0, lambda: self._show_new_products_dialog(new_products, products))

        threading.Thread(target=_run, daemon=True).start()

    def _show_new_products_dialog(self, new_products, all_products):
        """Yangi mahsulotlarni ko'rsatish dialogi."""
        dlg = tk.Toplevel(self.win)
        dlg.title("Yangi mahsulotlar topildi")
        dlg.configure(bg=CARD)
        dlg.resizable(True, True)
        dlg.grab_set()

        # Oyna o'lchami — katta
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        w, h = min(560, sw - 80), min(500, sh - 100)
        x = (sw - w) // 2
        y = max(40, (sh - h) // 2)
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.minsize(400, 350)

        # Sarlavha
        hdr = tk.Frame(dlg, bg='#4f46e5', pady=14, padx=20)
        hdr.pack(fill='x')
        tk.Label(hdr, text=f"🆕  {len(new_products)} ta yangi mahsulot topildi!",
                 font=('Segoe UI', 14, 'bold'), fg='white', bg='#4f46e5').pack()
        tk.Label(hdr, text="Printerga hali biriktirilmagan mahsulotlar",
                 font=('Segoe UI', 9), fg='#c7d2fe', bg='#4f46e5').pack()

        # Mahsulotlar ro'yxati
        lf = tk.Frame(dlg, bg=CARD, padx=16, pady=10)
        lf.pack(fill='both', expand=True)

        # Scroll listbox — katta
        lb_frame = tk.Frame(lf, bg=CARD, highlightbackground=BORDER,
                            highlightthickness=1)
        lb_frame.pack(fill='both', expand=True)
        sb2 = tk.Scrollbar(lb_frame, orient='vertical')
        lb = tk.Listbox(lb_frame, yscrollcommand=sb2.set,
                        bg='white', fg=FG, font=('Segoe UI', 11),
                        relief='flat', bd=6, selectmode='extended',
                        activestyle='none')
        sb2.config(command=lb.yview)
        sb2.pack(side='right', fill='y')
        lb.pack(side='left', fill='both', expand=True)

        # Kategoriya bo'yicha guruhlash
        from collections import defaultdict
        by_cat = defaultdict(list)
        for p in new_products:
            by_cat[p.get('category_name') or 'Boshqa'].append(p)

        for cat, prods in sorted(by_cat.items()):
            lb.insert('end', f"  ── {cat} ──")
            lb.itemconfig('end', foreground='#4f46e5', selectbackground='white')
            for p in prods:
                lb.insert('end', f"    •  {p['name']}")

        # Info xabar
        tk.Label(lf,
                 text="ℹ️  Printerga biriktirish uchun printer ustida ✎ Tahrirlash tugmasini bosing.",
                 font=('Segoe UI', 9), fg=FGD, bg=CARD, anchor='w',
                 wraplength=500, justify='left').pack(fill='x', pady=(10,0))

        # Tugmalar
        tk.Frame(dlg, bg=BORDER, height=1).pack(fill='x')
        bf = tk.Frame(dlg, bg='#f8fafc', padx=16, pady=10); bf.pack(fill='x')
        tk.Button(bf, text="  Yopish  ", command=dlg.destroy,
                  bg='#4f46e5', fg='white', font=('Segoe UI', 10, 'bold'),
                  relief='flat', padx=24, pady=6, cursor='hand2',
                  activebackground='#4338ca', activeforeground='white').pack(side='right')

        count_txt = f"✓ {len(new_products)} ta yangi mahsulot mavjud"
        self._logline(f"🆕 {count_txt}")

        # Oyna o'rtaga
        dlg.update_idletasks()
        pw = self.win.winfo_x() + (self.win.winfo_width()  - dlg.winfo_reqwidth())  // 2
        ph = self.win.winfo_y() + (self.win.winfo_height() - dlg.winfo_reqheight()) // 2
        dlg.geometry(f"+{pw}+{ph}")

    def _do_logout(self):
        if self.agent.running:
            self.agent.stop()
        do_logout()
        self.agent.reload()
        self._printers = []
        self._show_login()

    # ── DATA ─────────────────────────────────────────────────
    def _test_conn(self):
        ok, msg = self.agent.test()
        (messagebox.showinfo if ok else messagebox.showerror)(
            "✓ OK" if ok else "✗ Xato", msg, parent=self.win)

    # ── PRINTER TABLE ────────────────────────────────────────
    def _refresh_tbl(self):
        for r in self._tree.get_children(): self._tree.delete(r)
        for p in self._printers:
            conn = p.get('connection','auto')
            if conn=='network':   addr=f"{p.get('ip','')}:{p.get('port',9100)}"; ct='🌐 Tarmoq'
            elif conn=='wifi':    addr=f"{p.get('ip','')}:{p.get('port',9100)}"; ct='📶 WiFi'
            elif conn=='usb':     addr=p.get('usb',''); ct='🖨 USB'
            else:                 addr='(serverdan)';   ct='☁ Auto'
            pids = p.get('product_ids', [])
            pnames = p.get('product_names', {})
            if pids:
                names = [pnames.get(str(pid), pnames.get(pid, f'#{pid}')) for pid in pids]
                prod_txt = f"✓ {len(pids)} ta: {', '.join(names[:2])}{'...' if len(names)>2 else ''}"
            else:
                prod_txt = "— barcha"
            admin_txt = "✦ Admin" if p.get('is_admin', False) else ""
            self._tree.insert('','end', iid=p['id'],
                               values=(p.get('label',''), p.get('name',''), admin_txt, ct, addr,
                                       f"{p.get('paper_width',80)}mm", prod_txt))

    def _on_tree_select(self, event=None):
        """Printer tanlaganda mahsulotlarni pastda ko'rsatish"""
        p = self._sel()
        if not p:
            self._prod_detail.config(
                text="Printer tanlang — mahsulotlar ko'rinadi", fg=FGD)
            return
        pids = p.get('product_ids', [])
        pnames = p.get('product_names', {})
        pname = p.get('name', '')
        if not pids:
            self._prod_detail.config(
                text=f"🖨  {pname}:  barcha mahsulotlar (filter yo'q)", fg=FGD)
            return
        names = [pnames.get(str(pid), pnames.get(pid, f'#{pid}')) for pid in pids]
        self._prod_detail.config(
            text=f"🖨  {pname}  →  " + "  |  ".join(names),
            fg='#4f46e5')

    def _sel(self):
        s = self._tree.selection()
        if not s: return None
        return next((p for p in self._printers if p['id']==s[0]), None)

    def _creds(self):
        """Agent credentials tuple for PrinterDlg"""
        a = self.agent
        if a.server_url and a.username and a.business_id:
            return (a.server_url, a.username, a.password, a.business_id)
        return None

    def _auto_detect_printers(self):
        """USB printerlarni avtomatik aniqlash va drayver o'rnatish"""
        self._logline("🔍 Printerlar qidirilmoqda va drayverlar o'rnatilmoqda...")

        def _do():
            printers, messages = detect_and_install_printers()

            def _show():
                for m in messages:
                    tag = 'ok' if '✓' in m else ('error' if '✕' in m or '❌' in m else None)
                    self._logline(m, tag)
                self._refresh_tbl()

                final = local_printers()
                if final:
                    msg = f"Topilgan printerlar ({len(final)}):\n\n"
                    for i, p in enumerate(final, 1):
                        msg += f"  {i}. {p}\n"
                    if printers:
                        msg += f"\n✓ {len(printers)} ta yangi printer o'rnatildi!"
                    msg += "\n'+ Qo'shish' tugmasini bosib printer sozlang."
                    messagebox.showinfo("Printerlar", msg, parent=self.win)
                else:
                    self._show_driver_help()

            self.win.after(0, _show)

        threading.Thread(target=_do, daemon=True).start()

    def _show_driver_help(self):
        """Printer topilmaganda drayver o'rnatish qo'llanmasi"""
        DRIVER_URL = "https://www.xprintertech.com/all-products/thermal-receipt-printer-driver-download"

        dlg = tk.Toplevel(self.win)
        dlg.title("Printer drayverini o'rnatish")
        dlg.geometry("520x420")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.transient(self.win)
        dlg.grab_set()

        # Sarlavha
        hdr = tk.Frame(dlg, bg=RED, padx=16, pady=10)
        hdr.pack(fill='x')
        tk.Label(hdr, text="⚠  Printer topilmadi", font=('Segoe UI',13,'bold'),
                 fg='white', bg=RED).pack(anchor='w')

        body = tk.Frame(dlg, bg=BG, padx=20, pady=12)
        body.pack(fill='both', expand=True)

        txt = ("Kompyuteringizda printer drayveri o'rnatilmagan.\n"
               "Quyidagi qadamlarni bajaring:\n")
        tk.Label(body, text=txt, font=('Segoe UI',10), fg=FG, bg=BG,
                 justify='left', anchor='w').pack(fill='x', pady=(0,8))

        steps = [
            ("1️⃣", "Printeringizni USB kabel bilan kompyuterga ulang"),
            ("2️⃣", "Quyidagi havola orqali printeringizning drayverini yuklab oling:"),
            ("3️⃣", "Yuklangan faylni ishga tushirib drayverni o'rnating"),
            ("4️⃣", "O'rnatish tugagach, ushbu dasturda '🔍 Avtomatik topish' tugmasini bosing"),
        ]
        for num, step in steps:
            row = tk.Frame(body, bg=BG)
            row.pack(fill='x', pady=3)
            tk.Label(row, text=num, font=('Segoe UI',10), fg=FG, bg=BG,
                     width=3).pack(side='left', anchor='n')
            tk.Label(row, text=step, font=('Segoe UI',10), fg=FG, bg=BG,
                     wraplength=430, justify='left', anchor='w').pack(side='left', fill='x')

        # Havola tugmasi
        link_frame = tk.Frame(body, bg=BG)
        link_frame.pack(fill='x', pady=(8,4))
        tk.Label(link_frame, text="   ", bg=BG).pack(side='left')
        link_btn = tk.Button(link_frame,
            text="🌐  XPrinter drayverlarini yuklab olish",
            font=('Segoe UI',10,'bold'), fg='white', bg='#2563eb',
            activeforeground='white', activebackground='#1d4ed8',
            relief='flat', padx=16, pady=6, cursor='hand2',
            command=lambda: __import__('webbrowser').open(DRIVER_URL))
        link_btn.pack(side='left')

        # URL ko'rsatish
        tk.Label(body, text=DRIVER_URL,
                 font=('Consolas',8), fg='#6366f1', bg=BG,
                 cursor='hand2').pack(anchor='w', padx=28, pady=(2,8))

        # Qo'shimcha yo'riqnoma
        note = tk.Frame(body, bg='#fef3c7', padx=12, pady=8)
        note.pack(fill='x', pady=(4,0))
        tk.Label(note, text="💡 Maslahat:", font=('Segoe UI',9,'bold'),
                 fg='#92400e', bg='#fef3c7', anchor='w').pack(fill='x')
        tk.Label(note,
                 text=("Saytda printeringiz modelini tanlang (masalan: XP-80C, XP-58IIH).\n"
                       "Agar modelni bilmasangiz — printer orqa tomonidagi yorliqqa qarang.\n"
                       "Drayverni o'rnatgandan keyin kompyuterni qayta ishga tushiring."),
                 font=('Segoe UI',9), fg='#78350f', bg='#fef3c7',
                 wraplength=440, justify='left', anchor='w').pack(fill='x')

        # Yopish tugmasi
        tk.Button(dlg, text="Tushundim", font=('Segoe UI',10,'bold'),
                  fg='white', bg='#4f46e5', relief='flat',
                  padx=24, pady=6, cursor='hand2',
                  command=dlg.destroy).pack(pady=12)

    def _show_help(self):
        """Yordam oynasi — to'liq qo'llanma"""
        dlg = tk.Toplevel(self.win)
        dlg.title("Yordam — Nonbor Print Agent")
        dlg.geometry("620x580")
        dlg.configure(bg=BG)
        dlg.resizable(False, True)
        dlg.transient(self.win)
        dlg.grab_set()

        # Sarlavha
        hdr = tk.Frame(dlg, bg='#4f46e5', padx=16, pady=12)
        hdr.pack(fill='x')
        tk.Label(hdr, text="📖  Yordam — Nonbor Print Agent",
                 font=('Segoe UI',14,'bold'), fg='white', bg='#4f46e5').pack(anchor='w')
        tk.Label(hdr, text="Dastur qanday ishlaydi va qanday sozlanadi",
                 font=('Segoe UI',9), fg='#c7d2fe', bg='#4f46e5').pack(anchor='w')

        # Scrollable content
        canvas = tk.Canvas(dlg, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(dlg, orient='vertical', command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw', width=598)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        # Mouse wheel scroll
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), 'units')
        canvas.bind_all('<MouseWheel>', _on_mousewheel)
        dlg.bind('<Destroy>', lambda e: canvas.unbind_all('<MouseWheel>'))

        body = scroll_frame
        pad = {'padx': 16, 'pady': (0, 4)}

        def section(title, icon='📌'):
            f = tk.Frame(body, bg='#e0e7ff', padx=12, pady=6)
            f.pack(fill='x', **pad, pady=(12, 4))
            tk.Label(f, text=f"{icon}  {title}", font=('Segoe UI',11,'bold'),
                     fg='#312e81', bg='#e0e7ff').pack(anchor='w')

        def text(content):
            tk.Label(body, text=content, font=('Segoe UI',9), fg=FG, bg=BG,
                     wraplength=560, justify='left', anchor='w').pack(fill='x', **pad)

        # ═══ 1. DASTUR HAQIDA ═══
        section("Dastur haqida", "ℹ️")
        text("Nonbor Print Agent — buyurtmalarni avtomatik chop etish dasturi.\n"
             "Dastur serverdan yangi buyurtmalarni tekshiradi va ulangan\n"
             "printerga avtomatik chop etadi. Restoran, kafe, do'kon uchun.")

        # ═══ 2. BIRINCHI MARTA ISHGA TUSHIRISH ═══
        section("Birinchi marta ishga tushirish", "🚀")
        text("1. Dasturni ishga tushiring\n"
             "2. Server manzilini kiriting (admin beradi)\n"
             "3. Login va parolni kiriting\n"
             "4. 'Kirish' tugmasini bosing\n"
             "5. Muvaffaqiyatli kirganingizdan keyin asosiy sahifa ochiladi")

        # ═══ 3. PRINTER SOZLASH ═══
        section("Printer sozlash", "🖨")
        text("Printerni ulash va sozlash:\n\n"
             "1. Printerni kompyuterga USB kabel bilan ulang\n"
             "2. '🔍 Avtomatik topish' tugmasini bosing\n"
             "   — Dastur printerni avtomatik topadi\n"
             "   — Agar topmasa, drayver o'rnatish yo'riqnomasi ko'rsatiladi\n\n"
             "3. '+ Qo'shish' tugmasini bosing\n"
             "4. Printer sozlamalarini kiriting:\n"
             "   • Yorliq — printer nomi (masalan: Oshxona)\n"
             "   • Printer nomi — serverdagi nom bilan bir xil bo'lsin\n"
             "   • Ulanish turi — USB, Tarmoq yoki WiFi\n"
             "   • Qog'oz kengligi — 80mm yoki 58mm\n"
             "5. Mahsulotlarni tanlang — qaysi taomlar shu printerda chop etilsin\n"
             "6. 'Saqlash' bosing")

        # ═══ 4. ULANISH TURLARI — BATAFSIL ═══
        section("🔌  USB orqali ulash (eng oson)", "🔌")
        text("USB kabel bilan printerdan kompyuterga to'g'ridan-to'g'ri ulash.\n"
             "Bu eng sodda va ishonchli usul.\n\n"
             "Qadamlar:\n"
             "1. Printerni USB kabel bilan kompyuterga ulang\n"
             "2. Printerni yoqing (orqa tomonidagi tugma)\n"
             "3. Windows avtomatik tanimasligi mumkin — 30 soniya kuting\n"
             "4. Dasturda '🔍 Avtomatik topish' tugmasini bosing\n"
             "5. Agar printer topilsa — ro'yxatda paydo bo'ladi\n"
             "6. Ro'yxatdan printerni tanlab, 'Qo'shish' bosing\n\n"
             "Agar printer ro'yxatda ko'rinmasa:\n"
             "  → Drayver o'rnatish kerak (pastda 'Drayver o'rnatish' bo'limiga qarang)\n"
             "  → USB kabelni boshqa portga ulang\n"
             "  → Printerni o'chirib qayta yoqing\n\n"
             "Windows tekshirish:\n"
             "  → Boshqarish paneli → Qurilmalar va printerlar\n"
             "  → Printeringiz shu ro'yxatda bormi tekshiring\n"
             "  → Agar '!' belgisi bo'lsa — drayver muammo")

        section("🌐  Tarmoq (LAN kabel) orqali ulash", "🌐")
        text("Printer Ethernet (LAN) kabel bilan routerga ulangan.\n"
             "Bir nechta kompyuter bitta printerdan foydalanishi mumkin.\n\n"
             "1-qadam: Printerni tarmoqqa ulash\n"
             "  • Printerning orqa tomonidagi LAN portiga kabel ulang\n"
             "  • Kabelning ikkinchi uchini router/switchga ulang\n"
             "  • Printerni yoqing\n\n"
             "2-qadam: Printer IP manzilini aniqlash\n"
             "  • Ko'p printerlarda 'Feed' tugmasini 3-5 soniya bosib turing\n"
             "  • Self-test cheki chiqadi — unda IP manzil yozilgan\n"
             "  • Masalan: 192.168.1.87\n"
             "  • Agar IP topilmasa — printer menyusidan qarang\n"
             "  • Ba'zi printerlar DHCP bilan avtomatik IP oladi\n\n"
             "3-qadam: Dasturda sozlash\n"
             "  • Printer qo'shishda ulanish turini 'Tarmoq' tanlang\n"
             "  • IP manzilni kiriting: 192.168.1.87\n"
             "  • Port: 9100 (standart, o'zgartirmang)\n"
             "  • '⚡ Test' bosib tekshiring\n\n"
             "Muhim:\n"
             "  → Kompyuter va printer BIR tarmoqda bo'lishi shart\n"
             "  → Printer IP si o'zgarmesligi uchun statik IP qo'ying\n"
             "  → Router sozlamalarida printerga doimiy IP berish:\n"
             "     Routerga kiring → DHCP → Address Reservation\n"
             "     Printer MAC → 192.168.1.87 ga biriktiring")

        section("📡  WiFi orqali ulash", "📡")
        text("Printer WiFi orqali tarmoqqa ulangan.\n"
             "Kabel talab qilinmaydi, lekin WiFi signal yaxshi bo'lishi kerak.\n\n"
             "1-qadam: Printerni WiFi ga ulash\n"
             "  • Printerni yoqing\n"
             "  • Printer menyusiga kiring (tugmalar bilan)\n"
             "  • WiFi sozlamasini toping\n"
             "  • WiFi tarmog'ingiz nomini (SSID) tanlang\n"
             "  • Parolni kiriting\n"
             "  • Ba'zi printerlarda WPS tugma bor — routerda\n"
             "    WPS bosib, printerda ham WPS bosing\n\n"
             "2-qadam: IP manzilni aniqlash\n"
             "  • 'Feed' tugmasini 3-5 soniya bosib turing\n"
             "  • Self-test chekida WiFi IP manzil ko'rsatiladi\n"
             "  • Masalan: 192.168.1.105\n"
             "  • Agar 0.0.0.0 bo'lsa — WiFi ga ulanmagan\n\n"
             "3-qadam: Dasturda sozlash\n"
             "  • Ulanish turini 'WiFi' tanlang\n"
             "  • IP manzilni kiriting\n"
             "  • Port: 9100\n"
             "  • '⚡ Test' bosib tekshiring\n\n"
             "Muhim:\n"
             "  → Kompyuter va printer BIR WiFi tarmog'ida bo'lsin\n"
             "  → WiFi signal kuchli joyga qo'ying\n"
             "  → Printer WiFi uzilsa — qayta ulanmaydi,\n"
             "     printerni o'chirib yoqing\n"
             "  → Ishonchli ish uchun LAN kabel tavsiya etiladi")

        section("☁  Bulutli (Cloud) printer", "☁")
        text("Printer serverga to'g'ridan-to'g'ri ulangan.\n"
             "Kompyuter o'chiq bo'lsa ham server orqali chop etish mumkin.\n\n"
             "Bu usul faqat qo'llab-quvvatlanadigan printerlarda ishlaydi.\n\n"
             "Sozlash:\n"
             "  • Admin panelda printerni 'Cloud' turida qo'shing\n"
             "  • Server avtomatik printerni topadi\n"
             "  • Agentda alohida sozlash shart emas\n\n"
             "Afzalliklari:\n"
             "  → Kompyuter yoqilmasa ham ishlaydi\n"
             "  → Internet orqali istalgan joydan boshqarish\n\n"
             "Kamchiliklari:\n"
             "  → Internet uzilsa — chop etilmaydi\n"
             "  → Barcha printerlar qo'llab-quvvatlamaydi")

        section("⚙  Qaysi ulanish turini tanlash kerak?", "⚙")
        text("Vaziyatga qarab tavsiya:\n\n"
             "✅ 1 ta kompyuter, 1 ta printer → USB (eng oson)\n"
             "✅ Bir nechta kompyuter, 1 printer → Tarmoq (LAN)\n"
             "✅ Kabel tortish imkoni yo'q → WiFi\n"
             "✅ Kompyuter yo'q, faqat server → Cloud\n\n"
             "Ishonchlilik tartibi:\n"
             "  1. USB — eng ishonchli, kabel orqali\n"
             "  2. Tarmoq (LAN) — ishonchli, tez\n"
             "  3. WiFi — qulay, lekin uzilishi mumkin\n"
             "  4. Cloud — internet kerak\n\n"
             "Ko'p sotuvchilar uchun USB tavsiya etiladi —\n"
             "drayver o'rnatib, dasturda '🔍 Avtomatik topish' bosish kifoya.")

        # ═══ 5. AGENT ISHGA TUSHIRISH ═══
        section("Agentni ishga tushirish", "▶")
        text("1. '▶ ISHGA TUSHIR' tugmasini bosing\n"
             "2. Agent har necha sekundda serverdan yangi buyurtmalarni tekshiradi\n"
             "3. Yangi buyurtma kelsa — avtomatik chop etadi\n"
             "4. To'xtatish uchun '⏹ TO'XTAT' bosing\n\n"
             "Agentni fon rejimda ishlatish:\n"
             "  • Oynani yopganingizda dastur tray ikonida qoladi\n"
             "  • Tray ikonda o'ng tugma bosib boshqarish mumkin")

        # ═══ 6. AVTOMATIK ISHGA TUSHISH ═══
        section("Kompyuter yoqilganda avtomatik ishga tushish", "⚡")
        text("Pastdagi 'Windows yonganda avtomatik ishga tushir'\n"
             "belgisini qo'ying.\n\n"
             "Shundan keyin kompyuter har yoqilganda dastur avtomatik\n"
             "ishga tushadi va buyurtmalarni chop eta boshlaydi.\n"
             "Qo'lda hech narsa qilish shart emas.")

        # ═══ 7. MAHSULOTLARNI YANGILASH ═══
        section("Mahsulotlarni yangilash", "🔄")
        text("Menyuga yangi taom qo'shilganda:\n\n"
             "1. '🔄 Mahsulotlarni yangilash' tugmasini bosing\n"
             "2. Yangi mahsulotlar ko'rsatiladi\n"
             "3. Kerakli printerni tanlab, yangi mahsulotlarni biriktiring")

        # ═══ 8. TEST CHOP ETISH ═══
        section("Test chop etish", "⚡")
        text("Printer to'g'ri ishlayotganini tekshirish:\n\n"
             "1. Printerlar jadvalidan printerni tanlang\n"
             "2. '⚡ Test' tugmasini bosing\n"
             "3. Test cheki chop etiladi\n"
             "4. Agar chiqmasa — ulanishni tekshiring")

        # ═══ 9. DRAYVER O'RNATISH ═══
        section("Printer drayveri o'rnatish", "📦")
        text("Agar printer topilmasa — drayver o'rnatish kerak:\n\n"
             "1. Printeringiz modelini aniqlang\n"
             "   (orqa tomonidagi yorliqqa qarang: XP-80C, XP-58IIH va h.k.)\n\n"
             "2. Drayver yuklab olish:\n"
             "   https://www.xprintertech.com/all-products/thermal-receipt-printer-driver-download\n\n"
             "3. Yuklangan faylni ishga tushirib o'rnating\n"
             "4. Kompyuterni qayta ishga tushiring\n"
             "5. Dasturda '🔍 Avtomatik topish' bosing")

        # ═══ 10. MUAMMOLAR VA YECHIMLAR ═══
        section("Muammolar va yechimlar", "🔧")
        text("❌ 'Server bilan aloqa yo'q'\n"
             "  → Server manzilini tekshiring\n"
             "  → Internet aloqasini tekshiring\n\n"
             "❌ 'Printer topilmadi'\n"
             "  → USB kabelni qayta ulang\n"
             "  → Printerni o'chirib-yoqing\n"
             "  → Drayver o'rnating (yuqoriga qarang)\n\n"
             "❌ 'Chop etishda xatolik'\n"
             "  → Printerda qog'oz borligini tekshiring\n"
             "  → Printer yoqilganligini tekshiring\n"
             "  → '⚡ Test' bilan tekshiring\n\n"
             "❌ 'Login xatolik'\n"
             "  → Login va parolni tekshiring\n"
             "  → Admin bilan bog'laning")

        # ═══ 11. ALOQA ═══
        section("Bog'lanish", "📞")
        text("Muammo yechilmasa admin bilan bog'laning.\n"
             "Dastur versiyasi: v4.0\n"
             "Ishlab chiqaruvchi: Nonbor.uz")

        # Yopish
        close_frame = tk.Frame(dlg, bg=BG, pady=8)
        close_frame.pack(fill='x', side='bottom')
        tk.Button(close_frame, text="Yopish", font=('Segoe UI',10,'bold'),
                  fg='white', bg='#4f46e5', relief='flat',
                  padx=24, pady=6, cursor='hand2',
                  command=dlg.destroy).pack()

    def _add(self):
        d = PrinterDlg(self.win, local_printers(), credentials=self._creds(), all_printers=self._printers)
        self.win.wait_window(d)
        if d.result:
            self._printers.append(d.result)
            save_printers(self._printers, self.agent.business_id)
            self.agent.printers = self._printers
            self._refresh_tbl()
            self._logline(f"[+ {d.result['name']}]", 'ok')
            # Backend bilan sync
            self._sync_printer_bg(d.result)

    def _edit(self):
        p = self._sel()
        if not p: return
        d = PrinterDlg(self.win, local_printers(), data=p, credentials=self._creds(), all_printers=self._printers)
        self.win.wait_window(d)
        if d.result:
            d.result['id'] = p['id']
            i = next(i for i,x in enumerate(self._printers) if x['id']==p['id'])
            self._printers[i] = d.result
            save_printers(self._printers, self.agent.business_id)
            self.agent.printers = self._printers
            self._refresh_tbl()
            # Backend bilan sync
            self._sync_printer_bg(d.result)

    def _sync_printer_bg(self, printer_data):
        """Background da backend bilan printer sync"""
        a = self.agent
        def _do():
            ok, pid, err = api_sync_printer(
                a.server_url, a.username, a.password, printer_data)
            n = len(printer_data.get('product_ids', []))
            if ok:
                self._logline(f"  ↑ '{printer_data['name']}' sync: {n} mahsulot", 'ok')
            else:
                self._logline(f"  ⚠ Sync xato: {err}", 'error')
        threading.Thread(target=_do, daemon=True).start()

    def _del(self):
        p = self._sel()
        if not p: return
        if messagebox.askyesno("","O'chirishni tasdiqlang?", parent=self.win):
            self._printers = [x for x in self._printers if x['id']!=p['id']]
            save_printers(self._printers, self.agent.business_id); self.agent.printers = self._printers
            self._refresh_tbl()

    def _tst(self):
        p = self._sel()
        if not p: return
        ok, err = do_print(p, f"==================\n   TEST\n==================\nPrinter: {p['name']}\n{datetime.now().strftime('%d.%m.%Y %H:%M')}\nNonbor Print Agent\n==================\n")
        if ok: messagebox.showinfo("✓","Test chek chop etildi!",parent=self.win)
        else:  messagebox.showerror("✗ Xato", err, parent=self.win)

    # ── AGENT ────────────────────────────────────────────────
    def _toggle(self):
        if self.agent.running:
            self.agent.stop()
        else:
            self.agent.printers = self._printers
            self.agent.start()
        self._update_ui()

    # ── STATUS ───────────────────────────────────────────────
    def _tick(self):
        self._update_ui()
        self.win.after(2000, self._tick)

    def _update_ui(self):
        a = self.agent
        if a.running:
            self._dot.config(fg='#16a34a')
            self._stlbl.config(text=f"Ishlayapti — {len(self._printers)} printer", fg='#16a34a')
            self._togbtn.config(text="⏹  TO'XTAT", bg=RED,
                                activebackground='#b91c1c')
        else:
            self._dot.config(fg=RED)
            self._stlbl.config(text="To'xtatilgan", fg=FG)
            self._togbtn.config(text="▶  ISHGA TUSHIR", bg=GREEN,
                                activebackground='#15803d')
        self._stats.config(text=f"✓ {a.printed}   ✗ {a.errors}")

    # ── LOG ──────────────────────────────────────────────────
    def _on_log(self, line, lvl='info'):
        try: self.win.after(0, self._logline, line, lvl)
        except: pass

    def _logline(self, line, lvl='info'):
        self._log.config(state='normal')
        tag = 'error' if lvl=='error' else ('ok' if '✓' in line or 'OK' in line else '')
        self._log.insert('end', line+'\n', tag)
        self._log.see('end')
        n = int(self._log.index('end').split('.')[0])
        if n > 400: self._log.delete('1.0',f'{n-300}.0')
        self._log.config(state='disabled')

    # ── AUTOSTART ────────────────────────────────────────────
    def _toggle_auto(self):
        try:
            set_autostart(self._auto.get())
            msg = "✓ Avtomatik yoqildi" if self._auto.get() else "O'chirildi"
            messagebox.showinfo("Autostart", msg, parent=self.win)
        except Exception as e:
            messagebox.showerror("Xato", str(e), parent=self.win)

    # ── WINDOW HIDE/SHOW ─────────────────────────────────────
    def show(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    def _hide(self):
        self.win.withdraw()
        if self._on_close: self._on_close()

    def _quit(self):
        if self.agent.running:
            if not messagebox.askyesno("Chiqish",
                    "Agent ishlayapti!\nYopsam buyurtmalar chop etilmaydi. Davom etsinmi?",
                    parent=self.win):
                return
        self.agent.stop()
        if HAS_TRAY and hasattr(self, '_tray_icon'):
            self._tray_icon.stop()
        self.win.destroy()

    def run(self):
        self.win.mainloop()

# ── MAIN ─────────────────────────────────────────────────────
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--minimized', action='store_true')
    args = ap.parse_args()

    agent  = Agent()
    sw     = SettingsWindow(agent)

    if HAS_TRAY:
        _icon_ref = [None]

        def make_icon_obj():
            def on_settings(icon, item):
                sw.win.after(0, sw.show)

            def on_toggle(icon, item):
                def _do():
                    if agent.running: agent.stop()
                    else:
                        sw._collect(); save_config(agent)
                        agent.start()
                    # Update icon
                    icon.icon = make_tray_image(agent.running)
                sw.win.after(0, _do)

            def on_quit(icon, item):
                icon.stop()
                agent.stop()
                sw.win.after(0, sw.win.destroy)

            menu = pystray.Menu(
                pystray.MenuItem("⚙ Sozlamalar", on_settings, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("▶/⏹  Start / Stop", on_toggle),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("✕ Chiqish", on_quit),
            )
            ico = pystray.Icon(
                "NonborPrintAgent",
                make_tray_image(False),
                "Nonbor Print Agent",
                menu
            )
            _icon_ref[0] = ico
            sw._tray_icon = ico

            # Update tray icon color when agent status changes
            def status_watcher():
                prev = False
                while True:
                    time.sleep(2)
                    if agent.running != prev:
                        prev = agent.running
                        try: ico.icon = make_tray_image(agent.running)
                        except: pass
            threading.Thread(target=status_watcher, daemon=True).start()

            return ico

        ico = make_icon_obj()
        # run_detached → runs in background thread, tkinter stays on main thread
        ico.run_detached()

    # --minimized: yashirin ishga tushish + agent start
    if args.minimized:
        sw.win.withdraw()
        agent.start()
    else:
        sw.win.deiconify()

    sw.run()


if __name__ == '__main__':
    main()
