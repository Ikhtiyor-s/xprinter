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


class OrderServiceListView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/order-service/list/?business_id=<id>"""

    def get(self, request):
        business_id = request.GET.get('business_id')
        qs = OrderService.objects.all().order_by('business_id', 'service_name')
        if business_id:
            qs = qs.filter(business_id=business_id)
        return Response({'success': True, 'result': [_order_service_dict(s) for s in qs]})



class OrderServiceCreateView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/order-service/create/"""

    def post(self, request):
        business_id = request.data.get('business_id')
        service_name = request.data.get('service_name', '').strip()
        api_url = request.data.get('api_url', '').strip()

        if not business_id or not service_name:
            return Response({
                'success': False,
                'error': 'business_id va service_name majburiy',
            }, status=status.HTTP_400_BAD_REQUEST)

        template_id = request.data.get('template_id')
        template = None
        if template_id:
            try:
                template = IntegrationTemplate.objects.get(pk=template_id)
            except IntegrationTemplate.DoesNotExist:
                pass

        svc = OrderService.objects.create(
            template=template,
            business_id=business_id,
            business_name=request.data.get('business_name', ''),
            service_name=service_name,
            api_url=api_url,
            api_secret=request.data.get('api_secret', ''),
            bot_token=request.data.get('bot_token', ''),
            poll_enabled=request.data.get('poll_enabled', False),
            poll_interval=request.data.get('poll_interval', 10),
            is_active=request.data.get('is_active', True),
        )
        return Response({'success': True, 'result': _order_service_dict(svc)}, status=status.HTTP_201_CREATED)



class OrderServiceUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    """PUT /api/v2/order-service/{id}/update/"""

    def put(self, request, pk):
        try:
            svc = OrderService.objects.get(pk=pk)
        except OrderService.DoesNotExist:
            return Response({'success': False, 'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)

        for field in ('business_name', 'service_name', 'api_url', 'api_secret',
                      'bot_token', 'poll_enabled', 'poll_interval', 'is_active'):
            if field in request.data:
                setattr(svc, field, request.data[field])
        svc.save()
        return Response({'success': True, 'result': _order_service_dict(svc)})

    patch = put



class OrderServiceDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    """DELETE /api/v2/order-service/{id}/delete/"""

    def delete(self, request, pk):
        try:
            svc = OrderService.objects.get(pk=pk)
        except OrderService.DoesNotExist:
            return Response({'success': False, 'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)
        svc.delete()
        return Response({'success': True})


# ============================================================
# INTEGRATION TEMPLATE CRUD (Integratsiya shablonlari)
# ============================================================

