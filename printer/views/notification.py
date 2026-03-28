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


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/notification/list/?business_id=X&is_read=false"""

    def get(self, request):
        qs = PrinterNotification.objects.all()
        biz_id, err = enforce_business_id(request)
        if err:
            return err
        biz = biz_id or request.query_params.get('business_id')
        if biz:
            qs = qs.filter(business_id=biz)
        is_read = request.query_params.get('is_read')
        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() == 'true')
        qs = qs[:50]
        return Response({
            'success': True,
            'result': PrinterNotificationSerializer(qs, many=True).data,
        })



class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/notification/unread-count/?business_id=X"""

    def get(self, request):
        qs = PrinterNotification.objects.filter(is_read=False)
        biz_id, err = enforce_business_id(request)
        if err:
            return err
        biz = biz_id or request.query_params.get('business_id')
        if biz:
            qs = qs.filter(business_id=biz)
        return Response({
            'success': True,
            'count': qs.count(),
        })



class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/notification/mark-read/
    Body: { ids: [1,2,3] }  yoki  { all: true, business_id: X }"""

    def post(self, request):
        ids = request.data.get('ids', [])
        mark_all = request.data.get('all', False)
        biz = request.data.get('business_id')

        if mark_all:
            qs = PrinterNotification.objects.filter(is_read=False)
            if biz:
                qs = qs.filter(business_id=biz)
            count = qs.update(is_read=True)
        elif ids:
            count = PrinterNotification.objects.filter(
                id__in=ids, is_read=False
            ).update(is_read=True)
        else:
            return Response({
                'success': False,
                'error': 'ids yoki all kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'marked': count})



class NotificationConfigSaveView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/notification-config/save/ — upsert"""

    def post(self, request):
        biz_id = request.data.get('business_id')
        if not biz_id:
            return Response({
                'success': False,
                'error': 'business_id kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        defaults = {
            'business_name': request.data.get('business_name', ''),
            'telegram_chat_id': request.data.get('telegram_chat_id', ''),
            'telegram_enabled': request.data.get('telegram_enabled', False),
            'cloud_timeout_seconds': request.data.get('cloud_timeout_seconds', 20),
        }
        # Masked token bo'lsa o'zgartirmaslik
        new_token = request.data.get('telegram_bot_token', '')
        if new_token and '***' not in new_token:
            defaults['telegram_bot_token'] = new_token

        obj, created = NotificationConfig.objects.update_or_create(
            business_id=biz_id,
            defaults=defaults,
        )
        return Response({
            'success': True,
            'created': created,
            'result': NotificationConfigSerializer(obj).data,
        })



class NotificationConfigDetailView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/notification-config/{business_id}/detail/"""

    def get(self, request, business_id):
        try:
            obj = NotificationConfig.objects.get(business_id=business_id)
        except NotificationConfig.DoesNotExist:
            return Response({'success': True, 'result': None})
        return Response({
            'success': True,
            'result': NotificationConfigSerializer(obj).data,
        })



class NotificationTestTelegramView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/notification-config/test-telegram/"""

    def post(self, request):
        bot_token = request.data.get('telegram_bot_token', '')
        chat_id = request.data.get('telegram_chat_id', '')

        if not bot_token or not chat_id:
            return Response({
                'success': False,
                'error': 'bot_token va chat_id kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        from .services.notification_service import send_telegram_message
        text = "\u2705 Test xabar - Nonbor Printer bildirishnomalar ishlayapti!"
        sent = send_telegram_message(bot_token, chat_id, text)

        return Response({
            'success': sent,
            'message': 'Xabar yuborildi' if sent else "Xabar yuborib bo'lmadi",
        })


# ============================================================
# AGENT WEB DASHBOARD
# ============================================================

