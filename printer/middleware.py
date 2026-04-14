"""API Key authentication middleware for xprinter"""
import os
from django.http import JsonResponse

API_SECRET_KEY = os.environ.get('API_SECRET_KEY', '')
if not API_SECRET_KEY:
    import warnings
    warnings.warn("API_SECRET_KEY muhit o'zgaruvchisi o'rnatilmagan! Barcha so'rovlar Basic Auth bilan ishlaydi.", RuntimeWarning)

# Auth talab qilmaydigan yo'llar
PUBLIC_PATHS = {'/', '/health', '/admin/login/'}
PUBLIC_PREFIXES = ('/static/', '/media/', '/admin/')


class ApiKeyMiddleware:
    """X-API-Key yoki Basic Auth tekshiruvchi middleware"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Public yo'llar
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return self.get_response(request)

        # OPTIONS (CORS preflight)
        if request.method == 'OPTIONS':
            return self.get_response(request)

        # X-API-Key header tekshirish (faqat kalit mavjud bo'lganda)
        api_key = request.headers.get('X-API-Key', '')
        if API_SECRET_KEY and api_key == API_SECRET_KEY:
            return self.get_response(request)

        # Basic Auth (mavjud agent auth) — backward compatible
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Basic '):
            import base64
            try:
                decoded = base64.b64decode(auth[6:]).decode()
                username, password = decoded.split(':', 1)
                from django.contrib.auth import authenticate
                user = authenticate(username=username, password=password)
                if user and user.is_active:
                    return self.get_response(request)
            except Exception:
                pass

        return JsonResponse(
            {'success': False, 'error': 'API kalit noto\'g\'ri yoki berilmagan'},
            status=401
        )
