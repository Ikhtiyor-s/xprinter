"""
Custom authentication va permission klasslari.
Agent, Webhook, va Admin uchun alohida auth mexanizmlar.
"""
import hmac
import logging

from django.conf import settings
from rest_framework import authentication, exceptions, permissions

from printer.models import AgentCredential

logger = logging.getLogger(__name__)


class AgentTokenAuthentication(authentication.BaseAuthentication):
    """Print Agent autentifikatsiyasi.
    Usul 1 (yangi): Authorization: Bearer <token>
    Usul 2 (eski):  Authorization: Agent <username>:<password>
    """

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        # 1. Bearer token (yangi usul)
        if auth_header.startswith('Bearer '):
            raw_token = auth_header[7:].strip()
            if raw_token:
                return self._auth_by_token(raw_token)

        # 2. Agent user:pass (eski usul — backward compat)
        if auth_header.startswith('Agent '):
            raw = auth_header[6:]
            if ':' in raw:
                username, password = raw.split(':', 1)
                return self._auth_by_password(username.strip(), password.strip())

        # 3. POST body
        username = (
            request.data.get('username', '') if hasattr(request, 'data') else ''
        ) or request.query_params.get('username', '')
        password = (
            request.data.get('password', '') if hasattr(request, 'data') else ''
        ) or request.query_params.get('password', '')
        if username and password:
            return self._auth_by_password(username.strip(), password.strip())

        return None

    def _auth_by_token(self, raw_token: str):
        from printer.models import AgentSession
        try:
            session = AgentSession.objects.select_related('credential').get(
                token=raw_token, is_active=True
            )
        except AgentSession.DoesNotExist:
            return None
        if not session.is_valid:
            session.is_active = False
            session.save(update_fields=['is_active'])
            return None
        cred = session.credential
        if not cred.is_active:
            return None
        return (AgentUser(cred), session)

    def _auth_by_password(self, username: str, password: str):
        if not username or not password:
            return None
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


def get_seller_business_id(request):
    """Request dan business_id olish — Agent yoki Admin user"""
    user = request.user
    if isinstance(user, AgentUser):
        return user.business_id
    # Django User — SellerProfile dan
    if hasattr(user, 'seller_profile'):
        return user.seller_profile.business_id
    # Superuser — query param dan
    if hasattr(user, 'is_superuser') and user.is_superuser:
        return request.query_params.get('business_id') or request.data.get('business_id')
    return None


def enforce_business_id(request):
    """business_id olish — (biz_id, None) yoki (None, None) tuple qaytaradi."""
    biz_id = get_seller_business_id(request)
    if not biz_id:
        biz_id = request.query_params.get('business_id') or request.data.get('business_id')
    return biz_id, None


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
