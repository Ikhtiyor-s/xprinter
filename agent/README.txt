==================================================
  NONBOR PRINT AGENT v2.1
  Printer integratsiyasi uchun Windows dastur
==================================================

BU DASTUR NIMA QILADI?
-----------------------
Nonbor tizimidan yangi buyurtmalar kelganda
avtomatik ravishda oshxona printeriga chop etadi.


O'RNATISH (2 xil usul)
========================

USUL 1: EXE FAYLI (tavsiya)
-----------------------------
Python o'rnatilmagan kompyuterlar uchun.

  1. NonborPrintAgent.exe va config.ini bir papkada bo'lsin
  2. config.ini ni Notepad bilan oching va to'ldiring
  3. NonborPrintAgent.exe ni ishga tushiring
  4. Dasturda Printer ro'yxatidan printeringizni tanlang
  5. "Saqlash" bosing, keyin "ISHGA TUSHIR" bosing

USUL 2: PYTHON ORQALI
---------------------
  1. setup.bat ni ishga tushiring (bir martalik)
  2. start.bat ni ishga tushiring


DASTUR INTERFEYSI
==================

  Server URL   - Nonbor server manzili
  Business ID  - Biznes ID (admin beradi)
  Login/Parol  - API login ma'lumotlari
  Printer      - Lokal printer ro'yxati (yangilash tugmasi bilan)

  Ulanishni tekshir  - server bilan bog'lanishni test qilish
  Saqlash            - sozlamalarni config.ini ga saqlash
  ISHGA TUSHIR       - agentni yoqish
  AVTOMATIK          - Windows yonganda darhol ishlaydi


CONFIG.INI SOZLAMALARI
=======================

  [server]
  url = http://192.168.1.100:9000

  [business]
  id = 96

  [auth]
  username = admin
  password = parolingiz

  [printer]
  default_printer = XPrinter POS-80

  [settings]
  poll_interval = 3
  paper_width = 80


MUAMMOLAR VA YECHIMLAR
========================

  "Serverga ulanib bolmadi"
    - Server URL ni tekshiring (http:// bor, port togri)
    - Internet/tarmoq borligini tekshiring

  "Printer topilmadi"
    - Printer kompyuterda ornatilganligini tekshiring
    - Yangilash tugmasi bilan royxatni yangilang

  EXE ishlamayapti
    - config.ini va EXE bir papkada turadimi?
    - agent.log faylini oching - batafsil xatolik yozilgan


FAYLLAR
--------
  NonborPrintAgent.exe   - Asosiy dastur
  config.ini             - Sozlamalar
  agent.log              - Xatoliklar jurnali


ALOQA: nonbor.uz
==================================================
