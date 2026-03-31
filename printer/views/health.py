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


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            db_ok = True
        except Exception:
            db_ok = False
        return Response({
            'status': 'healthy' if db_ok else 'degraded',
            'database': 'ok' if db_ok else 'error',
        }, status=200 if db_ok else 503)
