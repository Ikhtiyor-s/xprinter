# Nonbor Print Agent - Mobile (Flutter)

Buyurtmalarni avtomatik chop etish uchun Android ilova.

## Talablar

- Flutter 3.38+ (stable)
- Android SDK 21+
- Java 17+

## Loyiha strukturasi

```
mobile/
  lib/
    main.dart                 # App entry, auto-login
    screens/
      login_screen.dart       # Server URL + login/parol
      dashboard_screen.dart   # Statistika, auto-polling
      settings_screen.dart    # Server sozlash, logout
    services/
      api_service.dart        # Xprinter API client
    theme/
      app_theme.dart          # Material 3, ranglar, shriftlar
  android/                    # Android native config
  pubspec.yaml                # Dependencies
```

## APK Build

```bash
cd mobile
flutter pub get
flutter build apk --release
```

APK: `build/app/outputs/flutter-apk/app-release.apk`

## Admin panelga joylashtirish

```bash
cp build/app/outputs/flutter-apk/app-release.apk /
  path/to/nonbor-admin/backend/app/downloads/NonborPrinter.apk
```

Admin panelda "Dastur yuklab olish" > "Android (APK)" tugmasi orqali yuklanadi.

## Xususiyatlar

- Material 3 dizayn (Inter font, gradient login)
- Auto-login (oldingi session saqlanadi)
- 5 sekundlik auto-polling (pending joblar)
- Server health check (aloqa holati)
- Basic Auth (xprinter API bilan mos)
- Statistika: pending / printed / error

## API integratsiya

| Endpoint | Vazifasi |
|----------|----------|
| `POST /agent/auth/` | Login |
| `GET /print-job/agent/poll/` | Pending joblar |
| `POST /print-job/agent/complete/` | Job tugadi |
| `GET /agent/menu/{id}/` | Menyu |
| `GET /health/` | Server holati |

## Windows EXE Build (agent/)

```bash
cd agent
pip install pyinstaller pywin32 pystray Pillow requests
pyinstaller --onefile --windowed --name NonborPrintAgent agent_app.py
```

EXE: `agent/dist/NonborPrintAgent.exe`
