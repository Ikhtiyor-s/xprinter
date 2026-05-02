import hmac
import logging
import os
import time as _time

from django.conf import settings as django_settings
from django.shortcuts import render
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from printer.permissions import XprinterApiKeyPermission
from rest_framework.views import APIView
from rest_framework.response import Response

from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token

from .authentication import (
    AgentTokenAuthentication,
    WebhookAuthentication,
    IsAgentAuthenticated,
    IsWebhookAuthenticated,
    validate_file_upload,
    get_seller_business_id,
    enforce_business_id,
)
from printer.models import SellerProfile
from printer.models import (
    Printer, PrinterCategory, PrinterProduct, PrintJob,
    NonborConfig, AgentCredential, IntegrationTemplate, OrderService,
    ReceiptTemplate, NotificationConfig, PrinterNotification,
)
from printer.serializers import (
    PrinterCreateSerializer,
    PrinterUpdateSerializer,
    PrinterListSerializer,
    PrinterDetailSerializer,
    PrinterCategorySerializer,
    PrinterCategoryAssignSerializer,
    PrinterCategoryBulkAssignSerializer,
    PrinterProductSerializer,
    PrinterProductAssignSerializer,
    PrinterProductBulkAssignSerializer,
    PrintJobSerializer,
    PrintOrderSerializer,
    WebhookSerializer,
    NonborConfigSerializer,
    NonborConfigCreateSerializer,
    NonborConfigUpdateSerializer,
    ReceiptTemplateSerializer,
    NotificationConfigSerializer,
    PrinterNotificationSerializer,
)
from printer.services.print_service import (
    print_order,
    retry_print_job,
    send_test_print,
    detect_system_printers,
)
from printer.services.nonbor_api import NonborAPI, poll_and_print

logger = logging.getLogger(__name__)


# ============================================================
# PRINTER CRUD
# ============================================================


class AdminTokenLoginView(APIView):
    """POST /api/v2/admin/login/
    Admin panel uchun token olish.
    {username, password} -> {token, user_id, business_ids}
    Django User model orqali autentifikatsiya."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "").strip()

        if not username or not password:
            return Response(
                {"error": "username va password kerak"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=username, password=password)
        if not user or not user.is_active:
            return Response(
                {"error": "Login yoki parol xato"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)

        # Seller profile dan business_id olish
        business_id = None
        business_name = ""
        is_superadmin = user.is_superuser
        try:
            profile = user.seller_profile
            business_id = profile.business_id
            business_name = profile.business_name
            is_superadmin = profile.is_superadmin or user.is_superuser
        except SellerProfile.DoesNotExist:
            if not user.is_superuser:
                return Response(
                    {"error": "Seller profili topilmadi. Admin bilan bog'laning."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        return Response({
            "success": True,
            "token": token.key,
            "user_id": user.id,
            "username": user.username,
            "business_id": business_id,
            "business_name": business_name,
            "is_superadmin": is_superadmin,
        })



class AdminTokenLogoutView(APIView):
    """POST /api/v2/admin/logout/ — tokenni o'chirish"""
    permission_classes = [XprinterApiKeyPermission]

    def post(self, request):
        try:
            request.user.auth_token.delete()
        except Exception:
            pass
        return Response({"success": True})


# ============================================================
# HEALTH CHECK
# ============================================================

