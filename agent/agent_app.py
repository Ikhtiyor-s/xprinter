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
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

CONFIG_FILE        = BASE_DIR / 'config.ini'
PRINTERS_FILE      = BASE_DIR / 'printers.json'
LOG_FILE           = BASE_DIR / 'agent.log'
SAVED_LOGINS_FILE  = BASE_DIR / 'saved_logins.json'

# ── SERVER URL (server_url.txt dan o'qiladi, aks holda default) ─────────
_SERVER_URL_FILE = BASE_DIR / 'server_url.txt'
def _load_server_url():
    if _SERVER_URL_FILE.exists():
        try:
            url = _SERVER_URL_FILE.read_text(encoding='utf-8').strip()
            if url: return url.rstrip('/')
        except: pass
    return "http://localhost:8080"

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
    import requests as _req; HAS_REQ = True
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
    c['settings'] = {'poll_interval': str(a.poll_interval)}
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f: c.write(f)

def is_logged_in():
    c = load_config()
    return bool(_cfg_get(c, 'auth', 'username') and _cfg_get(c, 'business', 'id'))

def do_logout():
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    if PRINTERS_FILE.exists():
        PRINTERS_FILE.unlink()

def load_saved_logins():
    if SAVED_LOGINS_FILE.exists():
        try:
            with open(SAVED_LOGINS_FILE, encoding='utf-8') as f: return json.load(f)
        except: pass
    return []

def save_login_to_history(username, password):
    logins = [l for l in load_saved_logins() if l.get('username') != username]
    logins.insert(0, {'username': username, 'password': password})
    with open(SAVED_LOGINS_FILE, 'w', encoding='utf-8') as f:
        json.dump(logins[:10], f, ensure_ascii=False)

def api_fetch_menu(server_url, username, password, business_id):
    """GET /api/v2/agent/menu/<business_id>/ → (ok, products, error)
    products: [{id, name, category_id, category_name}]"""
    try:
        full = f"{server_url}/api/v2/agent/menu/{business_id}/"
        params = {'username': username, 'password': password}
        if HAS_REQ:
            r = _req.get(full, params=params, timeout=15)
            try: data = r.json()
            except: return False, [], f"Server xatosi ({r.status_code})"
        else:
            import urllib.parse
            qs = urllib.parse.urlencode(params)
            req = urllib.request.Request(f"{full}?{qs}")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        if data.get('success'):
            return True, data.get('products', []), None
        return False, [], data.get('error', 'Noma\'lum xato')
    except Exception as e:
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
            'product_ids': printer_data.get('product_ids', []),
            'product_names': printer_data.get('product_names', {}),
        }
        if HAS_REQ:
            r = _req.post(full, json=payload, timeout=15)
            try: data = r.json()
            except: return False, None, f"Server xatosi ({r.status_code})"
        else:
            body = json.dumps(payload).encode()
            req = urllib.request.Request(full, data=body, method='POST')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        if data.get('success'):
            return True, data.get('printer_id'), None
        return False, None, data.get('error', 'Sync xato')
    except Exception as e:
        return False, None, str(e)


def api_agent_auth(username, password):
    """POST /api/v2/agent/auth/ → (ok, business_id, business_name, error)"""
    try:
        full = f"{SERVER_URL}/api/v2/agent/auth/"
        if HAS_REQ:
            r = _req.post(full, json={'username': username, 'password': password}, timeout=10)
            text = r.text.strip()
            if not text:
                return False, None, None, "Server bo'sh javob qaytardi (server ishlamayapti?)"
            try: data = r.json()
            except Exception: return False, None, None, f"Server xatosi ({r.status_code}): {text[:80]}"
        else:
            body = json.dumps({'username': username, 'password': password}).encode()
            req = urllib.request.Request(full, data=body, method='POST')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
                if not raw.strip(): return False, None, None, "Server bo'sh javob qaytardi"
                data = json.loads(raw)
        if data.get('success'):
            return True, str(data['business_id']), data.get('business_name', ''), None
        return False, None, None, data.get('error', 'Login yoki parol noto\'g\'ri')
    except Exception as e:
        return False, None, None, str(e)

def load_printers():
    if PRINTERS_FILE.exists():
        try:
            with open(PRINTERS_FILE, encoding='utf-8') as f: return json.load(f)
        except: pass
    return []

def save_printers(ps):
    with open(PRINTERS_FILE, 'w', encoding='utf-8') as f:
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
        return _req.get(full, auth=(u, p), timeout=10).json()
    req = urllib.request.Request(full)
    req.add_header('Authorization', 'Basic ' + base64.b64encode(f'{u}:{p}'.encode()).decode())
    with urllib.request.urlopen(req, timeout=10) as r: return json.loads(r.read())

def _post(url, u, p, path, data):
    full = f"{url.rstrip('/')}/api/v2/{path}"
    if HAS_REQ:
        return _req.post(full, json=data, auth=(u, p), timeout=10).json()
    body = json.dumps(data).encode()
    req = urllib.request.Request(full, data=body, method='POST')
    req.add_header('Authorization', 'Basic ' + base64.b64encode(f'{u}:{p}'.encode()).decode())
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=10) as r: return json.loads(r.read())

# ── PRINTER ──────────────────────────────────────────────────
def local_printers():
    if IS_WIN and HAS_WIN32:
        try:
            raw = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
            return [n for _,_,n,_ in raw]
        except: pass
    return []

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
    except Exception as e: return False, str(e)

def do_print(p_cfg, content):
    conn  = p_cfg.get('connection','auto')
    ip    = p_cfg.get('ip','')
    port  = p_cfg.get('port', 9100)
    usb   = p_cfg.get('usb','')
    width = int(p_cfg.get('paper_width', 80))
    data  = escpos(content, width)
    if conn == 'network' and ip: return print_net(ip, port, data)
    if usb: return (print_usb(usb, data) if IS_WIN else (False, "Linux USB"))
    return False, "Printer sozlanmagan"

# ── AGENT CORE ───────────────────────────────────────────────
class Agent:
    def __init__(self):
        self.running = False
        self.server_url = SERVER_URL
        self.business_id = ''
        self.business_name = ''
        self.username = ''
        self.password = ''
        self.poll_interval = 3
        self.printers = []
        self.printed = 0
        self.errors  = 0
        self._cbs = []
        self._thread = None
        self.reload()

    def reload(self):
        c = load_config()
        self.server_url    = SERVER_URL
        self.business_id   = _cfg_get(c,'business','id','')
        self.business_name = _cfg_get(c,'business','name','')
        self.username      = _cfg_get(c,'auth','username','')
        self.password      = _cfg_get(c,'auth','password','')
        self.poll_interval = int(_cfg_get(c,'settings','poll_interval','3'))
        self.printers      = load_printers()

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

    def _poll(self):
        try:
            r = _get(self.server_url, self.username, self.password,
                     'print-job/agent/poll/', {'business_id': self.business_id})
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
    c    = (0, 212, 170) if active else (200, 60, 60)
    # Printer body
    draw.rounded_rectangle([8,20,56,46], radius=4, fill=c)
    # Paper tray (top)
    draw.rounded_rectangle([18,10,46,24], radius=3, fill=c)
    # Paper output
    draw.rectangle([20,38,44,58], fill='white')
    draw.rectangle([24,44,40,48], fill=c)
    # Status dot
    dot = (0,230,120) if active else (255,80,80)
    draw.ellipse([42,24,54,36], fill=dot, outline='white', width=1)
    return img

# ── PRINTER DIALOG ───────────────────────────────────────────
class PrinterDlg(tk.Toplevel):
    def __init__(self, parent, local_ps, data=None, credentials=None):
        """
        credentials = (server_url, username, password, business_id)
        """
        super().__init__(parent)
        self.result     = None
        self._lps       = local_ps
        self._creds     = credentials  # (server_url, username, password, business_id)
        self._products  = []           # [{id, name, category_name}]
        self._checkvars = {}           # product_id → BooleanVar
        self._prod_loading = False
        self.title("Printer" + (" tahrirlash" if data else " qo'shish"))
        self.geometry("500x680")
        self.resizable(False, True)
        self.configure(bg='#1a1a2e')
        self.transient(parent); self.grab_set()
        self._build(data or {})
        self._sync()
        # Products ni background da yuklash
        if credentials:
            threading.Thread(target=self._load_products,
                             args=(data or {},), daemon=True).start()

    def _lbl(self, parent, text):
        return tk.Label(parent, text=text, width=16, anchor='w',
                        font=('Segoe UI',10), fg='#888', bg='#1a1a2e')

    def _entry(self, parent, val=''):
        e = tk.Entry(parent, font=('Segoe UI',10), bg='#16213e', fg='white',
                     insertbackground='white', relief='flat', bd=5)
        e.insert(0, val); return e

    def _build(self, d):
        p = dict(padx=20, pady=5)

        # ── Detected printers (auto-scan)
        dp = tk.Frame(self, bg='#0f3460', padx=12, pady=8)
        dp.pack(fill='x')
        dh = tk.Frame(dp, bg='#0f3460'); dh.pack(fill='x')
        tk.Label(dh, text="🔍 Topilgan printerlar",
                 font=('Segoe UI',9,'bold'), fg='#00d4aa', bg='#0f3460').pack(side='left')
        tk.Button(dh, text="🔄 Yangilash", command=self._refresh_detected,
                  bg='#16213e', fg='#aaa', relief='flat',
                  font=('Segoe UI',8), cursor='hand2', padx=6, pady=1).pack(side='right')
        self._det_frame = tk.Frame(dp, bg='#0f3460')
        self._det_frame.pack(fill='x', pady=(6,0))
        self._populate_detected()

        # ── Name
        r = tk.Frame(self, bg='#1a1a2e'); r.pack(fill='x', **p)
        self._lbl(r,"Printer nomi *").pack(side='left')
        self._name = self._entry(r, d.get('name',''))
        self._name.pack(side='left', fill='x', expand=True)
        tk.Label(self, text="  Serverda ko'rsatilgan nom bilan aynan mos bo'lsin",
                 font=('Segoe UI',8), fg='#555', bg='#1a1a2e').pack(anchor='w', padx=20)

        # Connection
        r2 = tk.Frame(self, bg='#1a1a2e'); r2.pack(fill='x', **p)
        self._lbl(r2,"Ulanish turi *").pack(side='left')
        self._conn = tk.StringVar(value=d.get('connection','network'))
        for v,t in [('network','🌐 Tarmoq (IP)'),('usb','🖨 USB/Windows'),('auto','☁ Auto')]:
            tk.Radiobutton(r2, text=t, variable=self._conn, value=v,
                           bg='#1a1a2e', fg='white', selectcolor='#0f3460',
                           activebackground='#1a1a2e', font=('Segoe UI',9),
                           command=self._sync).pack(side='left', padx=5)

        # IP
        self._nf = tk.Frame(self, bg='#1a1a2e')
        self._nf.pack(fill='x', padx=20)
        rn = tk.Frame(self._nf, bg='#1a1a2e'); rn.pack(fill='x', pady=3)
        self._lbl(rn,"IP manzil *").pack(side='left')
        self._ip   = self._entry(rn, d.get('ip',''))
        self._ip.pack(side='left', fill='x', expand=True)
        self._lbl(rn,"  Port").pack(side='left')
        self._port = self._entry(rn, str(d.get('port',9100)))
        self._port.config(width=7); self._port.pack(side='left')

        # USB
        self._uf = tk.Frame(self, bg='#1a1a2e')
        self._uf.pack(fill='x', padx=20)
        ru = tk.Frame(self._uf, bg='#1a1a2e'); ru.pack(fill='x', pady=3)
        self._lbl(ru,"Printer nomi *").pack(side='left')
        self._usb = tk.StringVar(value=d.get('usb',''))
        self._cb = ttk.Combobox(ru, textvariable=self._usb, font=('Segoe UI',10))
        self._cb['values'] = self._lps
        self._cb.pack(side='left', fill='x', expand=True)

        # Paper width
        rw = tk.Frame(self, bg='#1a1a2e'); rw.pack(fill='x', **p)
        self._lbl(rw,"Qog'oz kengligi").pack(side='left')
        self._pw = tk.StringVar(value=str(d.get('paper_width',80)))
        for v,t in [('80','80 mm'),('58','58 mm')]:
            tk.Radiobutton(rw, text=t, variable=self._pw, value=v,
                           bg='#1a1a2e', fg='white', selectcolor='#0f3460',
                           activebackground='#1a1a2e', font=('Segoe UI',9)).pack(side='left',padx=8)

        # ── Mahsulotlar bo'limi ──────────────────────────────────
        tk.Frame(self, bg='#0f3460', height=1).pack(fill='x', pady=(8,0))
        ph = tk.Frame(self, bg='#1a1a2e', padx=16, pady=5); ph.pack(fill='x')
        tk.Label(ph, text="🍽  Mahsulotlar",
                 font=('Segoe UI',10,'bold'), fg='#e0e0e0', bg='#1a1a2e').pack(side='left')
        self._prod_count_lbl = tk.Label(ph, text="",
                 font=('Segoe UI',8), fg='#555', bg='#1a1a2e')
        self._prod_count_lbl.pack(side='left', padx=6)
        abf = tk.Frame(ph, bg='#1a1a2e'); abf.pack(side='right')
        tk.Button(abf, text="☑ Barchasi", command=self._check_all,
                  bg='#0f3460', fg='#aaa', relief='flat',
                  font=('Segoe UI',8), cursor='hand2', padx=6, pady=1).pack(side='left', padx=2)
        tk.Button(abf, text="☐ Hech biri", command=self._uncheck_all,
                  bg='#0f3460', fg='#aaa', relief='flat',
                  font=('Segoe UI',8), cursor='hand2', padx=6, pady=1).pack(side='left', padx=2)

        # Scrollable mahsulotlar frame
        prod_container = tk.Frame(self, bg='#16213e', padx=16, pady=4)
        prod_container.pack(fill='both', expand=True, padx=16, pady=(0,4))

        self._prod_canvas = tk.Canvas(prod_container, bg='#0d1117',
                                       highlightthickness=0, height=180)
        vsb = ttk.Scrollbar(prod_container, orient='vertical',
                             command=self._prod_canvas.yview)
        self._prod_sf = tk.Frame(self._prod_canvas, bg='#0d1117')
        self._prod_sf.bind('<Configure>', lambda e: self._prod_canvas.configure(
            scrollregion=self._prod_canvas.bbox('all')))
        self._prod_win = self._prod_canvas.create_window(
            (0, 0), window=self._prod_sf, anchor='nw')
        self._prod_canvas.configure(yscrollcommand=vsb.set)
        self._prod_canvas.bind('<Configure>',
            lambda e: self._prod_canvas.itemconfigure(self._prod_win, width=e.width))
        self._prod_canvas.bind_all('<MouseWheel>',
            lambda e: self._prod_canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        vsb.pack(side='right', fill='y')
        self._prod_canvas.pack(side='left', fill='both', expand=True)

        # Status label (yuklanmoqda yoki hint)
        self._prod_status = tk.Label(self._prod_sf,
            text="⏳ Mahsulotlar yuklanmoqda..." if self._creds else
                 "ℹ  Mahsulotlar: tizimga kirish kerak",
            font=('Segoe UI',9), fg='#666', bg='#0d1117', anchor='w')
        self._prod_status.pack(fill='x', padx=8, pady=8)

        # Buttons
        bf = tk.Frame(self, bg='#1a1a2e'); bf.pack(fill='x', padx=20, pady=10)
        tk.Button(bf, text="✓ Saqlash", command=self._ok,
                  bg='#00b894', fg='white', font=('Segoe UI',10,'bold'),
                  relief='flat', padx=16, pady=5, cursor='hand2').pack(side='right', padx=(8,0))
        tk.Button(bf, text="Bekor", command=self.destroy,
                  bg='#0f3460', fg='white', font=('Segoe UI',10),
                  relief='flat', padx=14, pady=5, cursor='hand2').pack(side='right')

    def _populate_detected(self):
        for w in self._det_frame.winfo_children():
            w.destroy()
        if not self._lps:
            tk.Label(self._det_frame, text="  Hech qanday printer topilmadi",
                     font=('Segoe UI',8), fg='#666', bg='#0f3460').pack(anchor='w')
            return
        for pname in self._lps:
            btn = tk.Button(self._det_frame, text=f"🖨  {pname}",
                            command=lambda n=pname: self._select_detected(n),
                            bg='#16213e', fg='#e0e0e0', relief='flat',
                            font=('Segoe UI',9), anchor='w', cursor='hand2',
                            padx=8, pady=3, bd=0)
            btn.pack(fill='x', pady=1)
            btn.bind('<Enter>', lambda e, b=btn: b.config(bg='#1a1a2e'))
            btn.bind('<Leave>', lambda e, b=btn: b.config(bg='#16213e'))

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

    # ── Mahsulotlar ───────────────────────────────────────────
    def _load_products(self, existing_data):
        """Background thread: mahsulotlarni serverdan yuklab, UI ni yangilaydi"""
        su, uname, pwd, bid = self._creds
        bid_int = int(bid)
        ok, products, err = api_fetch_menu(su, uname, pwd, bid_int)
        self._products = products
        # Existing product_ids (edit mode)
        existing_ids = set(existing_data.get('product_ids', []))
        # UI yangilash (main thread da)
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
                font=('Segoe UI',8), fg='#e17055', bg='#0d1117', anchor='w',
                wraplength=380, justify='left')
            self._prod_status.pack(fill='x', padx=8, pady=8)
            self._prod_count_lbl.config(text="— xato")
            return
        if not products:
            self._prod_status = tk.Label(self._prod_sf,
                text="ℹ  Nonbor menyuda mahsulotlar yo'q. Avval Nonbor panel da mahsulot qo'shing.",
                font=('Segoe UI',8), fg='#888', bg='#0d1117', anchor='w',
                wraplength=380, justify='left')
            self._prod_status.pack(fill='x', padx=8, pady=8)
            self._prod_count_lbl.config(text="— 0 ta")
            return

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
                     font=('Segoe UI',9,'bold'), fg='#00d4aa', bg='#0d1117',
                     anchor='w').pack(fill='x', padx=4, pady=(6,2))
            for p in items:
                pid = p.get('id')
                pname = p.get('name', '')
                var = tk.BooleanVar(value=(pid in existing_ids))
                self._checkvars[pid] = var
                row = tk.Frame(self._prod_sf, bg='#0d1117')
                row.pack(fill='x', padx=4, pady=1)
                cb = tk.Checkbutton(row, variable=var,
                    text=f"  {pname}",
                    font=('Segoe UI',9), fg='#e0e0e0', bg='#0d1117',
                    selectcolor='#0f3460', activebackground='#0d1117',
                    activeforeground='#e0e0e0',
                    anchor='w', command=self._update_count)
                cb.pack(side='left', fill='x', expand=True)

        self._update_count()

    def _update_count(self):
        total = len(self._checkvars)
        selected = sum(1 for v in self._checkvars.values() if v.get())
        self._prod_count_lbl.config(
            text=f"— {selected}/{total} tanlangan",
            fg='#00d4aa' if selected else '#555')

    def _check_all(self):
        for v in self._checkvars.values(): v.set(True)
        self._update_count()

    def _uncheck_all(self):
        for v in self._checkvars.values(): v.set(False)
        self._update_count()

    def _sync(self):
        conn = self._conn.get()
        state_n = 'normal' if conn=='network' else 'disabled'
        state_u = 'normal' if conn=='usb'     else 'disabled'
        for w in self._nf.winfo_children():
            for c in w.winfo_children():
                try: c.config(state=state_n)
                except: pass
        for w in self._uf.winfo_children():
            for c in w.winfo_children():
                try: c.config(state=state_u)
                except: pass

    def _ok(self):
        name = self._name.get().strip()
        if not name:
            messagebox.showwarning("","Printer nomini kiriting!",parent=self); return
        conn = self._conn.get()
        if conn=='network' and not self._ip.get().strip():
            messagebox.showwarning("","IP kiriting!",parent=self); return
        if conn=='usb' and not self._usb.get().strip():
            messagebox.showwarning("","Printer tanlang!",parent=self); return

        # Tanlangan mahsulotlar
        product_ids = [pid for pid, var in self._checkvars.items() if var.get()]
        product_names = {pid: p.get('name','') for p in self._products
                         for pid2, var in self._checkvars.items()
                         if pid2 == p.get('id') and var.get()
                         for pid in [pid2]}

        self.result = {
            'id':           str(uuid.uuid4()),
            'name':         name,
            'connection':   conn,
            'ip':           self._ip.get().strip(),
            'port':         int(self._port.get().strip() or 9100),
            'usb':          self._usb.get().strip(),
            'paper_width':  int(self._pw.get()),
            'product_ids':  product_ids,
            'product_names': {str(p['id']): p['name']
                              for p in self._products
                              if p['id'] in product_ids},
        }
        self.destroy()

# ── SETTINGS WINDOW ──────────────────────────────────────────
BG='#1a1a2e'; BG2='#16213e'; BG3='#0f3460'
ACCENT='#00d4aa'; RED='#d63031'; GREEN='#00b894'
PURPLE='#6c5ce7'; ORANGE='#e17055'
FG='#e0e0e0'; FGD='#666'

class SettingsWindow:
    def __init__(self, agent: Agent, on_close_cb=None):
        self.agent      = agent
        self._on_close  = on_close_cb
        self._printers  = load_printers()
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
        return tk.Button(p, text=t, command=cmd, bg=bg, fg='white',
                         font=kw.get('font',('Segoe UI',9)), relief='flat',
                         padx=kw.get('padx',12), pady=4, cursor='hand2',
                         activebackground=bg, activeforeground='white')

    def _build(self):
        # ── Header (always shown)
        h = tk.Frame(self.win, bg=BG2, pady=12)
        h.pack(fill='x')
        tk.Label(h, text="🖨  NONBOR PRINT AGENT",
                 font=('Segoe UI',14,'bold'), fg=ACCENT, bg=BG2).pack()
        tk.Label(h, text="nonbor.uz  |  Printer agenti",
                 font=('Segoe UI',9), fg=FGD, bg=BG2).pack()

        # ── Footer (always shown)
        ft = tk.Frame(self.win, bg=BG2, pady=7, padx=16)
        ft.pack(fill='x', side='bottom')
        self._auto = tk.BooleanVar(value=get_autostart())
        ttk.Checkbutton(ft, text="Windows yonganda avtomatik ishga tushir",
                        variable=self._auto, command=self._toggle_auto).pack(side='left')
        self._btn(ft, "✕ Chiqish", '#2d2d2d', self._quit, padx=10).pack(side='right')

        # ── Content area
        self._content = tk.Frame(self.win, bg=BG)
        self._content.pack(fill='both', expand=True)

        if is_logged_in():
            self._show_main()
        else:
            self._show_login()

    # ── LOGIN FRAME ───────────────────────────────────────────
    def _show_login(self):
        self.win.geometry("440x380")
        if self._main_frame:
            self._main_frame.pack_forget()
        if self._login_frame:
            self._login_frame.destroy()

        f = tk.Frame(self._content, bg=BG)
        f.pack(expand=True)
        self._login_frame = f
        self._saved_logins = load_saved_logins()

        tk.Label(f, text="Admin tomonidan berilgan login va parolni kiriting",
                 font=('Segoe UI',9), fg=FGD, bg=BG, wraplength=340,
                 justify='center').pack(pady=(24,16))

        # Login (Combobox — saqlangan loginlar)
        lf = tk.Frame(f, bg=BG); lf.pack(pady=5)
        tk.Label(lf, text="Login", font=('Segoe UI',10), fg='#aaa', bg=BG,
                 width=8, anchor='e').pack(side='left')
        usernames = [l['username'] for l in self._saved_logins]
        self._l_user = ttk.Combobox(lf, values=usernames,
                                     font=('Segoe UI',12), width=22)
        self._l_user.pack(side='left', padx=(8,0))
        self._l_user.bind('<<ComboboxSelected>>', self._on_login_select)

        # Parol + ko'z tugmasi
        pf = tk.Frame(f, bg=BG); pf.pack(pady=5)
        tk.Label(pf, text="Parol", font=('Segoe UI',10), fg='#aaa', bg=BG,
                 width=8, anchor='e').pack(side='left')
        self._pass_visible = False
        self._l_pass = tk.Entry(pf, font=('Segoe UI',12), bg=BG2, fg=FG,
                                 insertbackground=FG, relief='flat', bd=6, width=20,
                                 show='●')
        self._l_pass.pack(side='left', padx=(8,0))
        self._l_eye = tk.Button(pf, text='👁', command=self._toggle_pass,
                                 bg=BG2, fg='#888', relief='flat',
                                 font=('Segoe UI',10), cursor='hand2', padx=4, bd=0)
        self._l_eye.pack(side='left', padx=(2,0))
        self._l_pass.bind('<Return>', lambda e: self._do_login())

        # Error label
        self._l_err = tk.Label(f, text='', font=('Segoe UI',9), fg=RED, bg=BG)
        self._l_err.pack(pady=(4,0))

        # Kirish button
        self._l_btn = tk.Button(f, text="▶  Kirish",
                                 command=self._do_login,
                                 bg=GREEN, fg='white',
                                 font=('Segoe UI',11,'bold'),
                                 relief='flat', padx=28, pady=8, cursor='hand2')
        self._l_btn.pack(pady=14)

        # Saved logins hint
        if self._saved_logins:
            tk.Label(f, text=f"💾 {len(self._saved_logins)} ta saqlangan login",
                     font=('Segoe UI',8), fg='#444', bg=BG).pack()

        self._l_user.focus()

    def _on_login_select(self, event=None):
        """Saqlangan logindan tanlaganda parolni avtomatik to'ldirish"""
        selected = self._l_user.get()
        for entry in self._saved_logins:
            if entry['username'] == selected:
                self._l_pass.delete(0, 'end')
                self._l_pass.insert(0, entry['password'])
                break

    def _toggle_pass(self):
        self._pass_visible = not self._pass_visible
        self._l_pass.config(show='' if self._pass_visible else '●')
        self._l_eye.config(fg=ACCENT if self._pass_visible else '#888')

    def _do_login(self):
        u = self._l_user.get().strip()
        p = self._l_pass.get().strip()
        if not u or not p:
            self._l_err.config(text="Login va parolni kiriting!")
            return
        self._l_btn.config(text="Tekshirilmoqda...", state='disabled')
        self._l_err.config(text='')
        self.win.update()

        ok, bid, bname, err = api_agent_auth(u, p)
        self._l_btn.config(text="▶  Kirish", state='normal')
        if not ok:
            self._l_err.config(text=f"✗ {err}")
            return

        self.agent.username      = u
        self.agent.password      = p
        self.agent.business_id   = bid
        self.agent.business_name = bname
        save_config(self.agent)
        save_login_to_history(u, p)
        self._printers = load_printers()
        self._show_main()

    # ── MAIN FRAME ────────────────────────────────────────────
    def _show_main(self):
        self.win.geometry("700x600")
        if self._login_frame:
            self._login_frame.pack_forget()
        if self._main_frame:
            self._main_frame.destroy()

        f = tk.Frame(self._content, bg=BG)
        f.pack(fill='both', expand=True)
        self._main_frame = f

        # Status bar
        sb = tk.Frame(f, bg=BG3, pady=9, padx=16)
        sb.pack(fill='x')
        self._dot   = tk.Label(sb, text="●", font=('Segoe UI',16), fg=RED, bg=BG3)
        self._dot.pack(side='left')
        self._stlbl = tk.Label(sb, text="To'xtatilgan",
                                font=('Segoe UI',10,'bold'), fg=FG, bg=BG3)
        self._stlbl.pack(side='left', padx=8)
        # Biznes nomi va username
        biz = self.agent.business_name or f"Biznes #{self.agent.business_id}"
        self._bizlbl = tk.Label(sb, text=f"👤 {self.agent.username}  |  {biz}",
                                 font=('Segoe UI',9), fg='#888', bg=BG3)
        self._bizlbl.pack(side='left', padx=12)
        self._stats = tk.Label(sb, text="", font=('Segoe UI',9), fg=FGD, bg=BG3)
        self._stats.pack(side='right', padx=8)
        self._togbtn = tk.Button(sb, text="▶  ISHGA TUSHIR",
                                  command=self._toggle,
                                  bg=GREEN, fg='white',
                                  font=('Segoe UI',10,'bold'),
                                  relief='flat', padx=16, pady=3, cursor='hand2')
        self._togbtn.pack(side='right')

        # User info row (chiqish)
        uf = tk.Frame(f, bg=BG, padx=16, pady=6); uf.pack(fill='x')
        self._btn(uf, "🔗 Server test", PURPLE, self._test_conn).pack(side='left')
        self._btn(uf, "⟳ Hisobdan chiqish", '#444', self._do_logout).pack(side='right')

        # Printers section
        tk.Frame(f, bg=BG3, height=1).pack(fill='x')
        ph = tk.Frame(f, bg=BG, padx=16, pady=7); ph.pack(fill='x')
        tk.Label(ph, text="Printerlar", font=('Segoe UI',10,'bold'), fg=FG, bg=BG).pack(side='left')
        tk.Label(ph, text="— server printer nomiga mos bo'lsin",
                 font=('Segoe UI',8), fg=FGD, bg=BG).pack(side='left', padx=6)
        ab = tk.Frame(ph, bg=BG); ab.pack(side='right')
        for t,bg,fn in [("+ Qo'shish",GREEN,self._add),
                         ("✎",BG3,self._edit),("⚡ Test",ORANGE,self._tst),
                         ("✕",RED,self._del)]:
            self._btn(ab,t,bg,fn,padx=8 if len(t)<4 else 12).pack(side='left',padx=2)

        # Treeview
        tf = tk.Frame(f, bg=BG, padx=16); tf.pack(fill='x')
        style = ttk.Style(); style.theme_use('default')
        style.configure('T.Treeview', background='#0d1117', foreground=FG,
                         fieldbackground='#0d1117', rowheight=24, font=('Segoe UI',9))
        style.configure('T.Treeview.Heading', background=BG3, foreground=ACCENT,
                         font=('Segoe UI',9,'bold'))
        style.map('T.Treeview', background=[('selected',BG3)])
        cols = ('name','conn','addr','width','prods')
        self._tree = ttk.Treeview(tf, style='T.Treeview',
                                   columns=cols, show='headings', height=5)
        for col,(hd,w) in zip(cols,[("Printer nomi",160),
                                     ("Ulanish",80),("Manzil",190),
                                     ("Qog'oz",60),("Mahsulotlar",140)]):
            self._tree.heading(col, text=hd)
            self._tree.column(col, width=w, anchor='w')
        self._tree.pack(fill='x')
        self._tree.bind('<Double-1>', lambda e: self._edit())
        self._tree.bind('<<TreeviewSelect>>', self._on_tree_select)

        # Mahsulotlar detail panel (tanlangan printer uchun)
        self._prod_panel = tk.Frame(f, bg=BG2, padx=16, pady=6)
        self._prod_panel.pack(fill='x', padx=16, pady=(2,0))
        self._prod_detail = tk.Label(self._prod_panel,
            text="Printer tanlang — mahsulotlar ko'rinadi",
            font=('Segoe UI',8), fg=FGD, bg=BG2, anchor='w',
            wraplength=620, justify='left')
        self._prod_detail.pack(fill='x')

        # Log
        tk.Frame(f, bg=BG3, height=1).pack(fill='x', pady=(8,0))
        lf2 = tk.Frame(f, bg=BG, padx=16, pady=4); lf2.pack(fill='both', expand=True)
        tk.Label(lf2, text="Faoliyat jurnali", font=('Segoe UI',8),
                 fg=FGD, bg=BG).pack(anchor='w')
        self._log = scrolledtext.ScrolledText(
            lf2, font=('Consolas',9), bg='#0d1117', fg='#58a6ff',
            relief='flat', bd=0, state='disabled', height=7)
        self._log.tag_config('error', foreground='#ff7b72')
        self._log.tag_config('ok',    foreground='#3fb950')
        self._log.pack(fill='both', expand=True)

        self._refresh_tbl()
        self._tick()

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
            elif conn=='usb':     addr=p.get('usb',''); ct='🖨 USB'
            else:                 addr='(serverdan)';   ct='☁ Auto'
            pids = p.get('product_ids', [])
            pnames = p.get('product_names', {})
            if pids:
                names = [pnames.get(str(pid), pnames.get(pid, f'#{pid}')) for pid in pids]
                prod_txt = f"✓ {len(pids)} ta: {', '.join(names[:2])}{'...' if len(names)>2 else ''}"
            else:
                prod_txt = "— barcha"
            self._tree.insert('','end', iid=p['id'],
                               values=(p.get('name',''), ct, addr,
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
                text=f"🖨  {pname}:  barcha mahsulotlar (filter yo'q)", fg='#888')
            return
        names = [pnames.get(str(pid), pnames.get(pid, f'#{pid}')) for pid in pids]
        self._prod_detail.config(
            text=f"🖨  {pname}  →  " + "  |  ".join(names),
            fg=ACCENT)

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

    def _add(self):
        d = PrinterDlg(self.win, local_printers(), credentials=self._creds())
        self.win.wait_window(d)
        if d.result:
            self._printers.append(d.result)
            save_printers(self._printers)
            self.agent.printers = self._printers
            self._refresh_tbl()
            self._logline(f"[+ {d.result['name']}]", 'ok')
            # Backend bilan sync
            self._sync_printer_bg(d.result)

    def _edit(self):
        p = self._sel()
        if not p: return
        d = PrinterDlg(self.win, local_printers(), data=p, credentials=self._creds())
        self.win.wait_window(d)
        if d.result:
            d.result['id'] = p['id']
            i = next(i for i,x in enumerate(self._printers) if x['id']==p['id'])
            self._printers[i] = d.result
            save_printers(self._printers)
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
            save_printers(self._printers); self.agent.printers = self._printers
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
            self._dot.config(fg=ACCENT)
            self._stlbl.config(text=f"Ishlayapti — {len(self._printers)} printer")
            self._togbtn.config(text="⏹  TO'XTAT", bg=RED)
        else:
            self._dot.config(fg=RED)
            self._stlbl.config(text="To'xtatilgan")
            self._togbtn.config(text="▶  ISHGA TUSHIR", bg=GREEN)
        self._stats.config(text=f"✓{a.printed}  ✗{a.errors}")

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
