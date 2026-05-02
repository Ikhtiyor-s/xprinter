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


class ReceiptTemplateListView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """GET /api/v2/receipt-template/list/?business_id="""

    def get(self, request):
        qs = ReceiptTemplate.objects.all().order_by('business_id')
        business_id = request.GET.get('business_id')
        if business_id:
            qs = qs.filter(business_id=business_id)
        return Response({
            'success': True,
            'result': ReceiptTemplateSerializer(qs, many=True).data,
        })



class ReceiptTemplateDetailView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """GET /api/v2/receipt-template/<business_id>/detail/"""

    def get(self, request, business_id):
        seller_biz = get_seller_business_id(request.user)
        if seller_biz and seller_biz != business_id:
            return Response({'success': False, 'error': 'Ruxsat berilmagan'}, status=403)
        try:
            tpl = ReceiptTemplate.objects.get(business_id=business_id)
        except ReceiptTemplate.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Shablon topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'success': True,
            'result': ReceiptTemplateSerializer(tpl).data,
        })



class ReceiptTemplateSaveView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """POST /api/v2/receipt-template/save/
    Upsert: (business_id + template_type) bo'yicha mavjud bo'lsa yangilaydi, yo'q bo'lsa yaratadi"""

    def post(self, request):
        business_id = request.data.get('business_id')
        template_type = request.data.get('template_type', 'delivery')
        if not business_id:
            return Response({
                'success': False,
                'error': 'business_id majburiy',
            }, status=status.HTTP_400_BAD_REQUEST)

        tpl, created = ReceiptTemplate.objects.get_or_create(
            business_id=business_id,
            template_type=template_type,
            defaults={'business_name': request.data.get('business_name', '')}
        )

        fields = [
            'business_name', 'header_text',
            'show_customer_info', 'show_other_printers',
            'show_comment', 'show_product_names',
            'footer_text', 'font_size', 'default_paper_width',
        ]
        for field in fields:
            if field in request.data:
                setattr(tpl, field, request.data[field])
        tpl.save()

        return Response({
            'success': True,
            'result': ReceiptTemplateSerializer(tpl).data,
            'created': created,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)



class ReceiptTemplateDeleteView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """DELETE /api/v2/receipt-template/<business_id>/delete/?template_type=delivery"""

    def delete(self, request, business_id):
        template_type = request.GET.get('template_type', '')
        qs = ReceiptTemplate.objects.filter(business_id=business_id)
        if template_type:
            qs = qs.filter(template_type=template_type)
        count = qs.count()
        if count == 0:
            return Response({
                'success': False,
                'error': 'Shablon topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)
        qs.delete()
        return Response({'success': True, 'deleted': count})


# ============================================================
# NOTIFICATION ENDPOINTS
# ============================================================

