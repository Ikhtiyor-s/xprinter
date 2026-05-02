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


class IntegrationTemplateListView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """GET /api/v2/integration-template/list/"""

    def get(self, request):
        qs = IntegrationTemplate.objects.all()
        if request.GET.get('active_only') == 'true':
            qs = qs.filter(is_active=True)
        return Response({'success': True, 'result': [_template_dict(t, request) for t in qs]})



class IntegrationTemplateCreateView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """POST /api/v2/integration-template/create/"""

    def post(self, request):
        name = request.data.get('name', '').strip()
        slug = request.data.get('slug', '').strip()

        if not name or not slug:
            return Response({
                'success': False,
                'error': 'name va slug majburiy',
            }, status=status.HTTP_400_BAD_REQUEST)

        if IntegrationTemplate.objects.filter(slug=slug).exists():
            return Response({
                'success': False,
                'error': f'"{slug}" slug allaqachon mavjud',
            }, status=status.HTTP_400_BAD_REQUEST)

        is_active = request.data.get('is_active', True)
        if isinstance(is_active, str):
            is_active = is_active.lower() in ('true', '1', 'yes')

        t = IntegrationTemplate.objects.create(
            name=name,
            slug=slug,
            description=request.data.get('description', ''),
            icon=request.data.get('icon', '🔗'),
            color=request.data.get('color', '#1890ff'),
            base_api_url=request.data.get('base_api_url', ''),
            default_poll_interval=int(request.data.get('default_poll_interval', 10)),
            is_active=is_active,
            sort_order=int(request.data.get('sort_order', 0)),
        )
        if 'logo' in request.FILES:
            is_valid, err = validate_file_upload(request.FILES['logo'])
            if not is_valid:
                return Response({'error': err}, status=status.HTTP_400_BAD_REQUEST)
            t.logo = request.FILES['logo']
            t.save()
        return Response({'success': True, 'result': _template_dict(t, request)}, status=status.HTTP_201_CREATED)



class IntegrationTemplateUpdateView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """PUT /api/v2/integration-template/{id}/update/"""

    def put(self, request, pk):
        try:
            t = IntegrationTemplate.objects.get(pk=pk)
        except IntegrationTemplate.DoesNotExist:
            return Response({'success': False, 'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)

        for field in ('name', 'slug', 'description', 'icon', 'color', 'base_api_url'):
            if field in request.data:
                setattr(t, field, request.data[field])
        if 'default_poll_interval' in request.data:
            t.default_poll_interval = int(request.data['default_poll_interval'])
        if 'sort_order' in request.data:
            t.sort_order = int(request.data['sort_order'])
        if 'is_active' in request.data:
            val = request.data['is_active']
            t.is_active = val if isinstance(val, bool) else str(val).lower() in ('true', '1', 'yes')
        if 'logo' in request.FILES:
            t.logo = request.FILES['logo']
        t.save()
        return Response({'success': True, 'result': _template_dict(t, request)})

    patch = put



class IntegrationTemplateDeleteView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """DELETE /api/v2/integration-template/{id}/delete/"""

    def delete(self, request, pk):
        try:
            t = IntegrationTemplate.objects.get(pk=pk)
        except IntegrationTemplate.DoesNotExist:
            return Response({'success': False, 'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)
        t.delete()
        return Response({'success': True})


# ============================================================
# RECEIPT TEMPLATE CRUD (Chek shablonlari)
# ============================================================

