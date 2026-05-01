"""API Key authentication middleware for xprinter"""
import os
import base64
import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)

API_SECRET_KEY = os.environ.get('API_SECRET_KEY', '')

# Auth talab qilmaydigan yo'llar
PUBLIC_PATHS = {'/', '/health', '/admin/login/'}
PUBLIC_PREFIXES = ('/static/', '/media/', '/admin/')


class ApiKeyMiddleware:
    """X-API-Key, Basic Auth yoki Agent Auth tekshiruvchi middleware"""

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

        # 1. X-API-Key header
        api_key = request.headers.get('X-API-Key', '')
        if API_SECRET_KEY and api_key == API_SECRET_KEY:
            return self.get_response(request)

        auth = request.headers.get('Authorization', '')

        # 2. Basic Auth — Django admin user
        if auth.startswith('Basic '):
            try:
                decoded  = base64.b64decode(auth[6:]).decode()
                username, password = decoded.split(':', 1)
                from django.contrib.auth import authenticate
                user = authenticate(username=username, password=password)
                if user and user.is_active:
                    request.user = user  # DRF IsAuthenticated uchun
                    return self.get_response(request)
            except Exception:
                pass

        # 3. Agent Auth — AgentCredential (mobile/desktop agent)
        if auth.startswith('Agent '):
            try:
                token = auth[6:]
                if ':' in token:
                    username, password = token.split(':', 1)
                    from printer.models import AgentCredential
                    cred = AgentCredential.objects.get(
                        username=username.strip(), is_active=True
                    )
                    if cred.check_password(password.strip()):
                        return self.get_response(request)
            except Exception:
                pass

        # 4. Webhook — X-Webhook-Secret bilan DRF WebhookAuthentication handle qiladi
        webhook_secret = request.headers.get('X-Webhook-Secret', '')
        if webhook_secret:
            return self.get_response(request)

        # 5. AllowAny endpoint — agent/auth body dan tekshiriladi
        if path.startswith('/api/v2/agent/auth'):
            return self.get_response(request)

        return JsonResponse(
            {'success': False, 'error': 'Autentifikatsiya talab qilinadi'},
            status=401,
        )
