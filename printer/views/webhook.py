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
from .models import SellerProfile

from .models import (
    Printer, PrinterCategory, PrinterProduct, PrintJob,
    NonborConfig, AgentCredential, IntegrationTemplate, OrderService,
    ReceiptTemplate, NotificationConfig, PrinterNotification,
)
from .serializers import (
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
from .services.print_service import (
    print_order,
    retry_print_job,
    send_test_print,
    detect_system_printers,
)
from .services.nonbor_api import NonborAPI, poll_and_print

logger = logging.getLogger(__name__)


# ============================================================
# PRINTER CRUD
# ============================================================


@method_decorator(csrf_exempt, name='dispatch')
class PrintWebhookView(APIView):
    authentication_classes = [WebhookAuthentication]
    permission_classes = [IsWebhookAuthenticated]
    """POST /api/v2/print-job/webhook/
    Nonbor backenddan webhook - buyurtma statusi o'zgarganda avtomatik chop etish"""

    def post(self, request):
        # Webhook secret tekshirish
        # Auth handled by WebhookAuthentication (hmac.compare_digest)

        serializer = WebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        state = data.get('state', '')

        # Faqat ACCEPTED statusda avtomatik chop etish
        if state != 'ACCEPTED':
            return Response({
                'success': True,
                'message': f'Status {state} - chop etish kerak emas',
                'printed': False,
            })

        business_id = data['business_id']

        # Avtomatik chop etish yoqilgan printerlar bormi?
        auto_printers = Printer.objects.filter(
            business_id=business_id,
            is_active=True,
            auto_print=True,
        ).exists()

        if not auto_printers:
            return Response({
                'success': True,
                'message': 'Avtomatik chop etish yoqilmagan',
                'printed': False,
            })

        order_data = {
            'order_id': data['order_id'],
            'order_number': data.get('order_number', str(data['order_id'])),
            'business_name': data.get('business_name', ''),
            'customer_name': data.get('customer_name', ''),
            'customer_phone': data.get('customer_phone', ''),
            'customer_address': data.get('customer_address', ''),
            'delivery_method': data.get('delivery_method', ''),
            'payment_method': data.get('payment_method', ''),
            'order_type': data.get('order_type', ''),
            'scheduled_time': data.get('scheduled_time', ''),
            'comment': data.get('comment', ''),
        }

        items = data.get('items', [])
        if not items:
            logger.warning(f"Webhook: order #{data['order_id']} items bo'sh")
            return Response({
                'success': True,
                'message': 'Buyurtmada taomlar yo\'q',
                'printed': False,
            })

        jobs = print_order(
            order_data=order_data,
            items=items,
            business_id=business_id,
        )

        completed = sum(1 for j in jobs if j.status == PrintJob.STATUS_COMPLETED)
        failed = sum(1 for j in jobs if j.status == PrintJob.STATUS_FAILED)

        logger.info(
            f"Webhook: order #{data['order_id']} → "
            f"{completed} chop etildi, {failed} xatolik"
        )

        return Response({
            'success': True,
            'message': f'{completed} ta printerga chop etildi',
            'printed': completed > 0,
            'jobs_count': len(jobs),
            'completed': completed,
            'failed': failed,
        })


from rest_framework.throttling import AnonRateThrottle

class AuthRateThrottle(AnonRateThrottle):
    rate = '5/minute'

