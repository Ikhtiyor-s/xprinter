"""
Custom authentication va permission klasslari.
Agent, Webhook, va Admin uchun alohida auth mexanizmlar.
"""
import hmac
import logging

from django.conf import settings
from rest_framework import authentication, exceptions, permissions

from .models import AgentCredential

logger = logging.getLogger(__name__)


class AgentTokenAuthentication(authentication.BaseAuthentication):
    """Print Agent autentifikatsiyasi.
    Header: Authorization: Agent <username>:<password>
    Yoki POST body: username + password
    """

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if auth_header.startswith('Agent '):
            token = auth_header[6:]
            if ':' not in token:
                return None
            username, password = token.split(':', 1)
        else:
            # POST body dan o'qish (agent auth endpoint uchun)
            username = (
                request.data.get('username', '') if hasattr(request, 'data') else ''
            ) or request.query_params.get('username', '')
            password = (
                request.data.get('password', '') if hasattr(request, 'data') else ''
            ) or request.query_params.get('password', '')

        if not username or not password:
            return None

        username = username.strip()
        password = password.strip()

        try:
            cred = AgentCredential.objects.get(username=username, is_active=True)
        except AgentCredential.DoesNotExist:
            return None

        if not cred.check_password(password):
            return None

        return (AgentUser(cred), cred)


class AgentUser:
    """Agent credential ni user-like object sifatida wrap qilish."""

    def __init__(self, credential):
        self.credential = credential
        self.business_id = credential.business_id
        self.username = credential.username
        self.is_authenticated = True
        self.is_active = True
        self.pk = credential.pk


class WebhookAuthentication(authentication.BaseAuthentication):
    """Webhook autentifikatsiyasi.
    Header: X-Webhook-Secret
    Constant-time comparison bilan.
    """

    def authenticate(self, request):
        webhook_secret = request.META.get('HTTP_X_WEBHOOK_SECRET', '')
        if not webhook_secret:
            return None

        expected = getattr(settings, 'WEBHOOK_SECRET', '')
        if not expected:
            raise exceptions.AuthenticationFailed('Webhook secret is not configured.')

        if not hmac.compare_digest(webhook_secret, expected):
            raise exceptions.AuthenticationFailed('Invalid webhook secret.')

        return (WebhookUser(), 'webhook')


class WebhookUser:
    """Webhook uchun user-like object."""

    def __init__(self):
        self.is_authenticated = True
        self.is_active = True
        self.username = 'webhook'
        self.pk = None


class IsAgentAuthenticated(permissions.BasePermission):
    """Agent credential bilan autentifikatsiya qilinganmi."""

    def has_permission(self, request, view):
        return (
            hasattr(request, 'user') and
            isinstance(request.user, AgentUser) and
            request.user.is_authenticated
        )


class IsWebhookAuthenticated(permissions.BasePermission):
    """Webhook secret bilan autentifikatsiya qilinganmi."""

    def has_permission(self, request, view):
        return (
            hasattr(request, 'user') and
            isinstance(request.user, WebhookUser)
        )


def validate_file_upload(uploaded_file, max_size_mb=5, allowed_types=None):
    """Fayl yuklashni xavfsiz tekshirish."""
    if allowed_types is None:
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml']

    max_bytes = max_size_mb * 1024 * 1024
    if uploaded_file.size > max_bytes:
        return False, f"Fayl hajmi {max_size_mb}MB dan oshmasligi kerak."

    if uploaded_file.content_type not in allowed_types:
        return False, f"Ruxsat berilmagan fayl turi: {uploaded_file.content_type}"

    name = uploaded_file.name
    if ".." in name or "/" in name or "\\" in name:
        return False, "Fayl nomi xavfsiz emas."

    return True, ""
