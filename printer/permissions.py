import os
from rest_framework.permissions import BasePermission

_API_KEY = os.environ.get('XPRINTER_API_KEY', '')


class XprinterApiKeyPermission(BasePermission):
    """
    Admin endpointlar uchun API key autentifikatsiyasi.
    Header: X-API-Key: <XPRINTER_API_KEY>
    """
    message = 'XPRINTER_API_KEY talab etiladi'

    def has_permission(self, request, view):
        if not _API_KEY:
            return False
        return request.headers.get('X-API-Key', '') == _API_KEY
