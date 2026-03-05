#!/usr/bin/env python3
"""
Nonbor Print Agent v3.0 - Ko'p printerli Windows GUI
Cheksiz printer qo'shish mumkin, mahsulotlarga qarab chop etadi.
"""

import os
import sys
import time
import uuid
import socket
import json
import threading
import logging
import configparser
from pathlib import Path
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# ============================================================
# BASE DIR
# ============================================================

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

CONFIG_FILE   = BASE_DIR / 'config.ini'
PRINTERS_FILE = BASE_DIR / 'printers.json'
LOG_FILE      = BASE_DIR / 'agent.log'

# ============================================================
# LOGGING
# ============================================================

fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger = logging.getLogger('nonbor_agent')
logger.setLevel(logging.INFO)
logger.addHandler(fh)

# ============================================================
# CONFIG  (server / auth / settings)
# ============================================================

def load_config():
    cfg = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        cfg.read(CONFIG_FILE, encoding='utf-8')
    return cfg

def cfg_get(cfg, sec, key, default=''):
    try:
        return cfg.get(sec, key)
    except Exception:
        return default

def save_config(agent):
    cfg = configparser.ConfigParser()
    cfg['server']   = {'url': agent.server_url}
    cfg['business'] = {'id': agent.business_id}
    cfg['auth']     = {'username': agent.username, 'password': agent.password}
    cfg['settings'] = {
        'poll_interval': str(agent.poll_interval),
    }
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        cfg.write(f)

# ============================================================
# PRINTERS CONFIG  (printers.json)
# ============================================================
# Printer structure:
# {
#   "id"         : "uuid",
#   "name"       : "Oshxona printer",   ← serverda ko'rsatilgan nom bilan mos kelishi kerak
#   "connection" : "network"|"usb"|"wifi"|"auto",
#   "ip"         : "192.168.1.100",
#   "port"       : 9100,
#   "usb"        : "XPrinter POS-80",
#   "paper_width": 80
# }

def load_printers():
    if PRINTERS_FILE.exists():
        try:
            with open(PRINTERS_FILE, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_printers(printers):
    with open(PRINTERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(printers, f, ensure_ascii=False, indent=2)

# ============================================================
# HTTP
# ============================================================

try:
    import requests as _req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import base64

def _http_get(server_url, username, password, path, params=None):
    url = f"{server_url.rstrip('/')}/api/v2/{path}"
    if params:
        url += '?' + '&'.join(f'{k}={v}' for k, v in params.items())
    if HAS_REQUESTS:
        r = _req.get(url, auth=(username, password), timeout=10)
        return r.json()
    req = urllib.request.Request(url)
    creds = base64.b64encode(f'{username}:{password}'.encode()).decode()
    req.add_header('Authorization', f'Basic {creds}')
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

def _http_post(server_url, username, password, path, data):
    url = f"{server_url.rstrip('/')}/api/v2/{path}"
    if HAS_REQUESTS:
        r = _req.post(url, json=data, auth=(username, password), timeout=10)
        return r.json()
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method='POST')
    creds = base64.b64encode(f'{username}:{password}'.encode()).decode()
    req.add_header('Authorization', f'Basic {creds}')
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

# ============================================================
# WINDOWS PRINTER
# ============================================================

IS_WINDOWS = sys.platform == 'win32'

try:
    import win32print
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

def get_local_printers():
    if IS_WINDOWS and HAS_WIN32:
        try:
            raw = win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            )
            return [name for _, _, name, _ in raw]
        except Exception:
            pass
    return []

# ESC/POS
_INIT     = b'\x1b\x40'
_CUT      = b'\x1d\x56\x00'
_FEED     = b'\x1b\x64\x03'
_BOLD_ON  = b'\x1b\x45\x01'
_BOLD_OFF = b'\x1b\x45\x00'
_LEFT     = b'\x1b\x61\x00'

def _escpos(text, paper_width=80):
    cmds = bytearray(_INIT)
    cw = 42 if paper_width == 80 else 32
    for line in text.split('\n'):
        bold = any(w in line for w in ['JAMI:', 'Buyurtma:', 'Tel:', '====', '! IZOH', 'Manzil:'])
        if '====' in line:
            cmds += _LEFT + ('=' * cw).encode()
        elif '----' in line:
            cmds += _LEFT + ('-' * cw).encode()
        else:
            if bold:
                cmds += _BOLD_ON
            cmds += _LEFT + line.encode('utf-8', errors='replace')
            if bold:
                cmds += _BOLD_OFF
        cmds += b'\n'
    cmds += _FEED + _CUT
    return bytes(cmds)

def _send_network(ip, port, data):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((ip, int(port)))
        s.sendall(data)
        s.close()
        return True, None
    except Exception as e:
        return False, str(e)

def _send_usb_win(name, data):
    if not HAS_WIN32:
        return False, "pywin32 kutubxonasi topilmadi"
    try:
        h = win32print.OpenPrinter(name)
        try:
            win32print.StartDocPrinter(h, 1, ("Nonbor", None, "RAW"))
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, data)
            win32print.EndPagePrinter(h)
            win32print.EndDocPrinter(h)
            return True, None
        finally:
            win32print.ClosePrinter(h)
    except Exception as e:
        return False, str(e)

def _send_usb_linux(path, data):
    try:
        with open(path, 'wb') as f:
            f.write(data)
        return True, None
    except Exception as e:
        return False, str(e)

def send_to_printer(conn, ip, port, usb, paper_width, content):
    """Printerga ESC/POS yuborish."""
    data = _escpos(content, int(paper_width))
    if conn in ('network', 'wifi') and ip:
        return _send_network(ip, port, data)
    if usb:
        return _send_usb_win(usb, data) if IS_WINDOWS else _send_usb_linux(usb, data)
    return False, "Printer sozlanmagan"

# ============================================================
# AGENT CORE
# ============================================================

class Agent:
    def __init__(self):
        self.running         = False
        self.server_url      = 'http://localhost:9000'
        self.business_id     = '1'
        self.username        = 'admin'
        self.password        = 'admin123'
        self.poll_interval   = 3
        self.printers        = []        # printers.json dan olinadi

        self.total_printed   = 0
        self.total_errors    = 0
        self._thread         = None
        self._log_cbs        = []
        self._reload()

    def _reload(self):
        cfg = load_config()
        self.server_url    = cfg_get(cfg, 'server',   'url',          'http://localhost:9000')
        self.business_id   = cfg_get(cfg, 'business', 'id',           '1')
        self.username      = cfg_get(cfg, 'auth',     'username',     'admin')
        self.password      = cfg_get(cfg, 'auth',     'password',     'admin123')
        self.poll_interval = int(cfg_get(cfg, 'settings', 'poll_interval', '3'))
        self.printers      = load_printers()

    def _local_printer(self, job):
        """Job uchun lokal printer sozlamalarini topish.

        Mos kelish tartibi:
          1. job['printer_name'] → printers.json dagi name bilan taqqoslash
          2. Topilmasa → job ning o'z ip/usb dan foydalanish (auto)
        """
        job_name = (job.get('printer_name') or '').strip().lower()
        for p in self.printers:
            if p.get('name', '').strip().lower() == job_name:
                return p
        return None  # auto - job o'z sozlamasini ishlatadi

    def _execute(self, job):
        p = self._local_printer(job)

        if p and p.get('connection') != 'auto':
            # Lokal sozlama topildi
            conn  = p.get('connection', 'network')
            ip    = p.get('ip', '')
            port  = p.get('port', 9100)
            usb   = p.get('usb', '')
            width = p.get('paper_width', 80)
        else:
            # Serverdan kelgan sozlamalar
            conn  = job.get('printer_connection', 'cloud')
            ip    = job.get('printer_ip', '')
            port  = job.get('printer_port', 9100)
            usb   = job.get('printer_usb', '')
            width = job.get('paper_width', 80)

        return send_to_printer(conn, ip, port, usb, width, job.get('content', ''))

    def _poll(self):
        try:
            resp = _http_get(
                self.server_url, self.username, self.password,
                'print-job/agent/poll/', {'business_id': self.business_id}
            )
        except Exception as e:
            self.log(f"Server bilan bog'lanib bo'lmadi: {e}", 'error')
            return

        if not resp.get('success'):
            self.log(f"Server xatolik: {resp.get('error', 'Nomalum')}", 'error')
            return

        jobs = resp.get('result', [])
        if not jobs:
            return

        self.log(f"{len(jobs)} ta yangi buyurtma!")

        for job in jobs:
            job_id   = job['id']
            order_id = job['order_id']
            pname    = job.get('printer_name', '?')

            self.log(f"  → #{order_id}  printer: {pname}")
            ok, err = self._execute(job)

            try:
                _http_post(
                    self.server_url, self.username, self.password,
                    'print-job/agent/complete/',
                    {'job_id': job_id,
                     'status': 'completed' if ok else 'failed',
                     'error':  err or ''}
                )
            except Exception as ex:
                self.log(f"  Serverga javob yuborib bo'lmadi: {ex}", 'error')

            if ok:
                self.total_printed += 1
                self.log(f"  ✓ #{order_id} [{pname}] — TAYYOR")
            else:
                self.total_errors += 1
                self.log(f"  ✗ #{order_id} [{pname}] — XATO: {err}", 'error')

    def _loop(self):
        while self.running:
            try:
                self._poll()
            except Exception as e:
                self.log(f"Kutilmagan xatolik: {e}", 'error')
            time.sleep(self.poll_interval)

    def start(self):
        if self.running:
            return
        self._reload()
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.log(f"Agent ishga tushdi. {len(self.printers)} ta printer sozlangan.")

    def stop(self):
        self.running = False
        self.log("Agent to'xtatildi.")

    def test_connection(self):
        try:
            resp = _http_get(
                self.server_url, self.username, self.password,
                'printer/list/', {'business_id': self.business_id}
            )
            srv_printers = resp.get('result', [])
            return True, f"OK! Serverda {len(srv_printers)} ta printer topildi."
        except Exception as e:
            return False, str(e)

    def log(self, msg, level='info'):
        ts   = datetime.now().strftime('%H:%M:%S')
        line = f"[{ts}] {msg}"
        getattr(logger, level if level in ('info', 'error', 'warning') else 'info')(msg)
        for cb in self._log_cbs:
            try:
                cb(line, level)
            except Exception:
                pass

# ============================================================
# COLORS / STYLES
# ============================================================

BG     = '#1a1a2e'
BG2    = '#16213e'
BG3    = '#0f3460'
ACCENT = '#00d4aa'
RED    = '#d63031'
GREEN  = '#00b894'
PURPLE = '#6c5ce7'
ORANGE = '#e17055'
FG     = '#e0e0e0'
FGD    = '#888888'
FONT   = ('Segoe UI', 10)
FONTB  = ('Segoe UI', 10, 'bold')

# ============================================================
# PRINTER ADD / EDIT DIALOG
# ============================================================

class PrinterDialog(tk.Toplevel):
    """Printer qo'shish / tahrirlash modal oynasi."""

    def __init__(self, parent, local_printers, data=None):
        super().__init__(parent)
        self.result = None
        self._local = local_printers

        is_edit = data is not None
        self.title("Printer tahrirlash" if is_edit else "Yangi printer qo'shish")
        self.geometry("460x380")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        self._build(data or {})
        self._on_conn_change()

    def _build(self, d):
        pad = dict(padx=20, pady=6)

        # Name
        row = tk.Frame(self, bg=BG)
        row.pack(fill='x', **pad)
        tk.Label(row, text="Printer nomi *", width=18, anchor='w',
                 font=FONT, fg=FGD, bg=BG).pack(side='left')
        self._name = tk.Entry(row, font=FONT, bg=BG2, fg=FG,
                               insertbackground=FG, relief='flat', bd=5)
        self._name.insert(0, d.get('name', ''))
        self._name.pack(side='left', fill='x', expand=True)

        tk.Label(self,
                 text="(Serverda ko'rsatilgan printer nomi bilan aynan mos bo'lishi kerak)",
                 font=('Segoe UI', 8), fg=FGD, bg=BG).pack(anchor='w', padx=20)

        # Connection type
        row2 = tk.Frame(self, bg=BG)
        row2.pack(fill='x', **pad)
        tk.Label(row2, text="Ulanish turi *", width=18, anchor='w',
                 font=FONT, fg=FGD, bg=BG).pack(side='left')
        self._conn = tk.StringVar(value=d.get('connection', 'network'))
        for val, txt in [('network', 'Tarmoq (IP)'), ('wifi', 'WiFi'), ('usb', 'USB / Windows'), ('auto', 'Auto (serverdan)')]:
            tk.Radiobutton(row2, text=txt, variable=self._conn, value=val,
                           bg=BG, fg=FG, selectcolor=BG3, activebackground=BG,
                           font=('Segoe UI', 9),
                           command=self._on_conn_change).pack(side='left', padx=4)

        # Network fields
        self._net_frame = tk.Frame(self, bg=BG)
        self._net_frame.pack(fill='x', padx=20)

        ip_row = tk.Frame(self._net_frame, bg=BG)
        ip_row.pack(fill='x', pady=3)
        tk.Label(ip_row, text="IP manzil *", width=18, anchor='w',
                 font=FONT, fg=FGD, bg=BG).pack(side='left')
        self._ip = tk.Entry(ip_row, font=FONT, bg=BG2, fg=FG,
                             insertbackground=FG, relief='flat', bd=5)
        self._ip.insert(0, d.get('ip', ''))
        self._ip.pack(side='left', fill='x', expand=True)

        pt_row = tk.Frame(self._net_frame, bg=BG)
        pt_row.pack(fill='x', pady=3)
        tk.Label(pt_row, text="Port", width=18, anchor='w',
                 font=FONT, fg=FGD, bg=BG).pack(side='left')
        self._port = tk.Entry(pt_row, font=FONT, bg=BG2, fg=FG,
                               insertbackground=FG, relief='flat', bd=5, width=10)
        self._port.insert(0, str(d.get('port', 9100)))
        self._port.pack(side='left')

        # USB fields
        self._usb_frame = tk.Frame(self, bg=BG)
        self._usb_frame.pack(fill='x', padx=20)

        usb_row = tk.Frame(self._usb_frame, bg=BG)
        usb_row.pack(fill='x', pady=3)
        tk.Label(usb_row, text="Printer nomi *", width=18, anchor='w',
                 font=FONT, fg=FGD, bg=BG).pack(side='left')
        self._usb_var = tk.StringVar(value=d.get('usb', ''))
        self._usb_cb  = ttk.Combobox(usb_row, textvariable=self._usb_var,
                                      font=FONT, state='normal')
        self._usb_cb['values'] = self._local
        self._usb_cb.pack(side='left', fill='x', expand=True)

        # Paper width
        pw_row = tk.Frame(self, bg=BG)
        pw_row.pack(fill='x', **pad)
        tk.Label(pw_row, text="Qog'oz kengligi", width=18, anchor='w',
                 font=FONT, fg=FGD, bg=BG).pack(side='left')
        self._pw = tk.StringVar(value=str(d.get('paper_width', 80)))
        for v, t in [('80', '80 mm'), ('58', '58 mm')]:
            tk.Radiobutton(pw_row, text=t, variable=self._pw, value=v,
                           bg=BG, fg=FG, selectcolor=BG3, activebackground=BG,
                           font=('Segoe UI', 9)).pack(side='left', padx=8)

        # Buttons
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill='x', padx=20, pady=16)
        tk.Button(bf, text="✓ Saqlash", command=self._save,
                  bg=GREEN, fg='white', font=FONTB, relief='flat',
                  padx=16, pady=5, cursor='hand2').pack(side='right', padx=(8, 0))
        tk.Button(bf, text="Bekor", command=self.destroy,
                  bg=BG3, fg=FG, font=FONT, relief='flat',
                  padx=14, pady=5, cursor='hand2').pack(side='right')

    def _on_conn_change(self):
        conn = self._conn.get()
        net_active = conn in ('network', 'wifi')
        for w in self._net_frame.winfo_children():
            for c in w.winfo_children():
                c.configure(state='normal' if net_active else 'disabled')
        for w in self._usb_frame.winfo_children():
            for c in w.winfo_children():
                try:
                    c.configure(state='normal' if conn == 'usb' else 'disabled')
                except Exception:
                    pass

    def _save(self):
        name = self._name.get().strip()
        if not name:
            messagebox.showwarning("Xato", "Printer nomini kiriting!", parent=self)
            return
        conn = self._conn.get()
        if conn in ('network', 'wifi') and not self._ip.get().strip():
            messagebox.showwarning("Xato", "IP manzilni kiriting!", parent=self)
            return
        if conn == 'usb' and not self._usb_var.get().strip():
            messagebox.showwarning("Xato", "Printer nomini tanlang!", parent=self)
            return

        self.result = {
            'id':          str(uuid.uuid4()),
            'name':        name,
            'connection':  conn,
            'ip':          self._ip.get().strip(),
            'port':        int(self._port.get().strip() or 9100),
            'usb':         self._usb_var.get().strip(),
            'paper_width': int(self._pw.get()),
        }
        self.destroy()

# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow:
    def __init__(self, agent: Agent):
        self.agent = agent
        agent._log_cbs.append(self._on_log)

        self.root = tk.Tk()
        self.root.title("Nonbor Print Agent v3.0")
        self.root.geometry("720x680")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        self._printers = load_printers()   # local printers list (editable)
        self._build()
        self._load_values()
        self._refresh_table()
        self._tick()

    # ── UI BUILD ─────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = tk.Frame(self.root, bg=BG2, pady=12)
        hdr.pack(fill='x')
        tk.Label(hdr, text="🖨  NONBOR PRINT AGENT",
                 font=('Segoe UI', 15, 'bold'), fg=ACCENT, bg=BG2).pack()
        tk.Label(hdr, text="Ko'p printerli oshxona integratsiyasi v3.0",
                 font=('Segoe UI', 9), fg=FGD, bg=BG2).pack()

        # Status
        st = tk.Frame(self.root, bg=BG3, pady=9, padx=18)
        st.pack(fill='x')
        self._dot   = tk.Label(st, text="●", font=('Segoe UI', 16), fg=RED, bg=BG3)
        self._dot.pack(side='left')
        self._stlbl = tk.Label(st, text="To'xtatilgan", font=FONTB, fg=FG, bg=BG3)
        self._stlbl.pack(side='left', padx=8)
        self._stats = tk.Label(st, text="", font=('Segoe UI', 9), fg=FGD, bg=BG3)
        self._stats.pack(side='right')
        self._togbtn = tk.Button(st, text="▶  ISHGA TUSHIR",
                                  command=self._toggle,
                                  bg=GREEN, fg='white', font=FONTB,
                                  relief='flat', padx=16, pady=3,
                                  cursor='hand2')
        self._togbtn.pack(side='right', padx=8)

        # ── Server sozlamalari (yig'ma qator)
        sf = tk.Frame(self.root, bg=BG, padx=18, pady=10)
        sf.pack(fill='x')

        self._entries = {}
        fields = [("Server URL", 'server_url', 36),
                  ("Biznes ID",  'business_id', 8),
                  ("Login",      'username',    14),
                  ("Parol",      'password',    14)]
        for lbl, key, w in fields:
            col = tk.Frame(sf, bg=BG)
            col.pack(side='left', padx=(0, 12))
            tk.Label(col, text=lbl, font=('Segoe UI', 8), fg=FGD, bg=BG).pack(anchor='w')
            hide = key == 'password'
            e = tk.Entry(col, font=FONT, bg=BG2, fg=FG, insertbackground=FG,
                         relief='flat', bd=5, width=w, show='*' if hide else '')
            e.pack()
            self._entries[key] = e

        brow = tk.Frame(sf, bg=BG)
        brow.pack(side='left', padx=(8, 0))
        tk.Label(brow, text=" ", font=('Segoe UI', 8), bg=BG).pack()  # spacer
        tk.Button(brow, text="💾", command=self._save_server,
                  bg=BG3, fg=FG, font=FONT, relief='flat',
                  padx=8, pady=3, cursor='hand2').pack(side='left', padx=2)
        tk.Button(brow, text="🔗 Test", command=self._test_conn,
                  bg=PURPLE, fg='white', font=FONT, relief='flat',
                  padx=8, pady=3, cursor='hand2').pack(side='left')

        # ── Printerlar bo'limi ──────────────────────────────
        sep = tk.Frame(self.root, bg=BG3, height=1)
        sep.pack(fill='x')

        pr_hdr = tk.Frame(self.root, bg=BG, padx=18, pady=8)
        pr_hdr.pack(fill='x')
        tk.Label(pr_hdr, text="Printerlar", font=FONTB, fg=FG, bg=BG).pack(side='left')
        tk.Label(pr_hdr,
                 text="(server printer nomiga mos bo'lishi kerak)",
                 font=('Segoe UI', 8), fg=FGD, bg=BG).pack(side='left', padx=8)

        # Action buttons
        ab = tk.Frame(pr_hdr, bg=BG)
        ab.pack(side='right')
        self._add_btn = self._mbtn(ab, "+ Qo'shish",   GREEN,  self._add_printer)
        self._add_btn.pack(side='left', padx=3)
        self._edt_btn = self._mbtn(ab, "✎ Tahrirlash", BG3,    self._edit_printer)
        self._edt_btn.pack(side='left', padx=3)
        self._tst_btn = self._mbtn(ab, "⚡ Test",      ORANGE, self._test_printer)
        self._tst_btn.pack(side='left', padx=3)
        self._del_btn = self._mbtn(ab, "✕ O'chirish",  RED,    self._del_printer)
        self._del_btn.pack(side='left', padx=3)

        # Treeview (table)
        tf = tk.Frame(self.root, bg=BG, padx=18)
        tf.pack(fill='x')

        cols = ('name', 'connection', 'address', 'width')
        self._tree = ttk.Treeview(tf, columns=cols, show='headings', height=6)

        style = ttk.Style()
        style.theme_use('default')
        style.configure('Treeview',
                         background='#0d1117', foreground=FG,
                         fieldbackground='#0d1117', rowheight=26,
                         font=FONT)
        style.configure('Treeview.Heading',
                         background=BG3, foreground=ACCENT,
                         font=FONTB)
        style.map('Treeview', background=[('selected', BG3)])

        hdrs = [("Printer nomi (server bilan mos)", 220),
                ("Ulanish",  100),
                ("Manzil",   220),
                ("Qog'oz",    80)]
        for col, (hdr, w) in zip(cols, hdrs):
            self._tree.heading(col, text=hdr)
            self._tree.column(col, width=w, anchor='w')

        self._tree.pack(fill='x')
        self._tree.bind('<Double-1>', lambda e: self._edit_printer())

        # ── Log ─────────────────────────────────────────────
        sep2 = tk.Frame(self.root, bg=BG3, height=1)
        sep2.pack(fill='x', pady=(8, 0))

        lf = tk.Frame(self.root, bg=BG, padx=18, pady=4)
        lf.pack(fill='both', expand=True)
        tk.Label(lf, text="Faoliyat jurnali", font=('Segoe UI', 9),
                 fg=FGD, bg=BG).pack(anchor='w')
        self._log = scrolledtext.ScrolledText(
            lf, font=('Consolas', 9), bg='#0d1117', fg='#58a6ff',
            relief='flat', bd=0, state='disabled', height=8)
        self._log.tag_config('error', foreground='#ff7b72')
        self._log.tag_config('ok',    foreground='#3fb950')
        self._log.pack(fill='both', expand=True)

        # Footer
        foot = tk.Frame(self.root, bg=BG2, pady=7, padx=18)
        foot.pack(fill='x', side='bottom')
        self._auto_var = tk.BooleanVar(value=self._check_autostart())
        ttk.Checkbutton(foot,
                        text="Windows yonganda avtomatik ishga tushir",
                        variable=self._auto_var,
                        command=self._toggle_autostart).pack(side='left')
        tk.Label(foot, text="nonbor.uz  v3.0", font=('Segoe UI', 9),
                 fg=FGD, bg=BG2).pack(side='right')

    def _mbtn(self, parent, text, bg, cmd):
        return tk.Button(parent, text=text, command=cmd,
                         bg=bg, fg='white', font=('Segoe UI', 9),
                         relief='flat', padx=10, pady=3, cursor='hand2')

    # ── VALUES ───────────────────────────────────────────────

    def _load_values(self):
        a = self.agent
        for key, val in [('server_url', a.server_url), ('business_id', a.business_id),
                          ('username', a.username), ('password', a.password)]:
            self._entries[key].delete(0, 'end')
            self._entries[key].insert(0, val)

    def _collect_server(self):
        a = self.agent
        a.server_url    = self._entries['server_url'].get().strip()
        a.business_id   = self._entries['business_id'].get().strip()
        a.username      = self._entries['username'].get().strip()
        a.password      = self._entries['password'].get().strip()

    def _save_server(self):
        self._collect_server()
        save_config(self.agent)
        self._append_log("[Server sozlamalari saqlandi]", 'ok')

    def _test_conn(self):
        self._collect_server()
        ok, msg = self.agent.test_connection()
        if ok:
            messagebox.showinfo("✓ Muvaffaqiyatli", msg, parent=self.root)
        else:
            messagebox.showerror("✗ Xatolik", msg, parent=self.root)

    # ── PRINTER TABLE ────────────────────────────────────────

    def _refresh_table(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        for p in self._printers:
            conn = p.get('connection', 'auto')
            if conn == 'network':
                addr = f"{p.get('ip', '')}:{p.get('port', 9100)}"
                ctype = '🌐 Tarmoq'
            elif conn == 'wifi':
                addr = f"{p.get('ip', '')}:{p.get('port', 9100)}"
                ctype = '📶 WiFi'
            elif conn == 'usb':
                addr  = p.get('usb', '')
                ctype = '🖨 USB'
            else:
                addr  = '(serverdan)'
                ctype = '☁ Auto'
            self._tree.insert('', 'end', iid=p['id'],
                               values=(p.get('name', ''), ctype, addr,
                                       f"{p.get('paper_width', 80)} mm"))

    def _selected_printer(self):
        sel = self._tree.selection()
        if not sel:
            return None
        pid = sel[0]
        return next((p for p in self._printers if p['id'] == pid), None)

    def _add_printer(self):
        dlg = PrinterDialog(self.root, get_local_printers())
        self.root.wait_window(dlg)
        if dlg.result:
            self._printers.append(dlg.result)
            save_printers(self._printers)
            self._refresh_table()
            self.agent.printers = self._printers
            self._append_log(f"[Printer qo'shildi: {dlg.result['name']}]", 'ok')

    def _edit_printer(self):
        p = self._selected_printer()
        if not p:
            messagebox.showinfo("", "Biror printerni tanlang.", parent=self.root)
            return
        dlg = PrinterDialog(self.root, get_local_printers(), data=p)
        self.root.wait_window(dlg)
        if dlg.result:
            dlg.result['id'] = p['id']   # ID saqlash
            idx = next(i for i, x in enumerate(self._printers) if x['id'] == p['id'])
            self._printers[idx] = dlg.result
            save_printers(self._printers)
            self._refresh_table()
            self.agent.printers = self._printers
            self._append_log(f"[Printer tahrirlandi: {dlg.result['name']}]", 'ok')

    def _del_printer(self):
        p = self._selected_printer()
        if not p:
            messagebox.showinfo("", "Biror printerni tanlang.", parent=self.root)
            return
        if messagebox.askyesno("O'chirish",
                                f"'{p['name']}' printerini o'chirish?",
                                parent=self.root):
            self._printers = [x for x in self._printers if x['id'] != p['id']]
            save_printers(self._printers)
            self._refresh_table()
            self.agent.printers = self._printers
            self._append_log(f"[Printer o'chirildi: {p['name']}]")

    def _test_printer(self):
        p = self._selected_printer()
        if not p:
            messagebox.showinfo("", "Biror printerni tanlang.", parent=self.root)
            return
        test_text = (
            "==========================================\n"
            "   NONBOR PRINT AGENT - TEST\n"
            "==========================================\n"
            f"Printer: {p['name']}\n"
            f"Sana: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            "------------------------------------------\n"
            "Printer muvaffaqiyatli ishlayapti!\n"
            "==========================================\n"
        )
        ok, err = send_to_printer(
            p.get('connection', 'auto'),
            p.get('ip', ''),
            p.get('port', 9100),
            p.get('usb', ''),
            p.get('paper_width', 80),
            test_text
        )
        if ok:
            messagebox.showinfo("✓ Test muvaffaqiyatli",
                                f"'{p['name']}' ga test chek chop etildi!",
                                parent=self.root)
            self._append_log(f"[Test OK: {p['name']}]", 'ok')
        else:
            messagebox.showerror("✗ Xatolik",
                                  f"Chop etib bo'lmadi:\n{err}",
                                  parent=self.root)
            self._append_log(f"[Test XATO: {p['name']} — {err}]", 'error')

    # ── AGENT TOGGLE ─────────────────────────────────────────

    def _toggle(self):
        if self.agent.running:
            self.agent.stop()
        else:
            self._collect_server()
            save_config(self.agent)
            self.agent.printers = self._printers
            self.agent.start()
        self._update_ui()

    # ── STATUS ───────────────────────────────────────────────

    def _tick(self):
        self._update_ui()
        self.root.after(2000, self._tick)

    def _update_ui(self):
        a = self.agent
        if a.running:
            self._dot.config(fg=ACCENT)
            self._stlbl.config(text=f"Ishlayapti  —  {len(self._printers)} ta printer")
            self._togbtn.config(text="⏹  TO'XTAT", bg=RED)
        else:
            self._dot.config(fg=RED)
            self._stlbl.config(text="To'xtatilgan")
            self._togbtn.config(text="▶  ISHGA TUSHIR", bg=GREEN)
        self._stats.config(text=f"✓ {a.total_printed}  ✗ {a.total_errors}")

    # ── LOG ──────────────────────────────────────────────────

    def _on_log(self, line, level='info'):
        self.root.after(0, self._append_log, line, level)

    def _append_log(self, line, level='info'):
        self._log.config(state='normal')
        tag = 'error' if level == 'error' else ('ok' if '✓' in line or 'OK' in line else None)
        self._log.insert('end', line + '\n', tag or '')
        self._log.see('end')
        n = int(self._log.index('end').split('.')[0])
        if n > 400:
            self._log.delete('1.0', f'{n-300}.0')
        self._log.config(state='disabled')

    # ── AUTOSTART ────────────────────────────────────────────

    def _startup_bat(self):
        ap = os.environ.get('APPDATA', '')
        return Path(ap) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup' / 'nonbor_agent.bat'

    def _check_autostart(self):
        return IS_WINDOWS and self._startup_bat().exists()

    def _toggle_autostart(self):
        bat = self._startup_bat()
        if self._auto_var.get():
            if getattr(sys, 'frozen', False):
                exe = f'"{sys.executable}"'
            else:
                exe = f'python "{BASE_DIR / "agent_gui.py"}"'
            try:
                bat.write_text(f'@echo off\nstart "" /min {exe} --minimized\n', encoding='utf-8')
                messagebox.showinfo("Autostart", "✓ Avtomatik ishga tushirish yoqildi!", parent=self.root)
            except Exception as e:
                messagebox.showerror("Xatolik", str(e), parent=self.root)
                self._auto_var.set(False)
        else:
            try:
                if bat.exists():
                    bat.unlink()
                messagebox.showinfo("Autostart", "O'chirildi.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Xatolik", str(e), parent=self.root)

    # ── CLOSE ────────────────────────────────────────────────

    def _on_close(self):
        if self.agent.running:
            if not messagebox.askyesno("Chiqish",
                                        "Agent ishlayapti!\nYopsam buyurtmalar chop etilmaydi.\nYopishni xohlaysizmi?",
                                        parent=self.root):
                return
        self.agent.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()

# ============================================================
# ENTRY POINT
# ============================================================

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--minimized', action='store_true')
    args = ap.parse_args()

    agent  = Agent()
    window = MainWindow(agent)

    if args.minimized and CONFIG_FILE.exists():
        agent.start()
        window.root.iconify()

    window.run()


if __name__ == '__main__':
    main()
