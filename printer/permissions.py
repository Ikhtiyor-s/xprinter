import os
from rest_framework.permissions import BasePermission


class XprinterApiKeyPermission(BasePermission):
    """
    Admin endpointlar uchun ruxsat:
    1. X-API-Key header (XPRINTER_API_KEY env)
    2. Django admin user (is_staff=True)
    """
    message = 'Autentifikatsiya talab etiladi'

    def has_permission(self, request, view):
        # 1. X-API-Key
        api_key = os.environ.get('XPRINTER_API_KEY', '') or os.environ.get('API_SECRET_KEY', '')
        if api_key and request.headers.get('X-API-Key', '') == api_key:
            return True

        # 2. Django admin (Basic Auth yoki Session)
        if request.user and request.user.is_authenticated and request.user.is_staff:
            return True

        return False
