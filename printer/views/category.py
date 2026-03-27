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


class PrinterCategoryAssignView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/printer-category/assign/ - Kategoriyani printerga ulash"""

    def post(self, request):
        serializer = PrinterCategoryAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        mapping = PrinterCategory.objects.create(
            printer_id=serializer.validated_data['printer_id'],
            category_id=serializer.validated_data['category_id'],
            category_name=serializer.validated_data.get('category_name', ''),
            business_id=serializer.validated_data['business_id'],
        )

        return Response({
            'success': True,
            'result': PrinterCategorySerializer(mapping).data,
        }, status=status.HTTP_201_CREATED)



class PrinterCategoryListView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/printer-category/list/?business_id=&printer_id="""

    def get(self, request):
        business_id = request.query_params.get('business_id')
        printer_id = request.query_params.get('printer_id')

        if not business_id:
            return Response({
                'success': False,
                'error': 'business_id parametri kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        qs = PrinterCategory.objects.filter(
            business_id=business_id,
        ).select_related('printer')

        if printer_id:
            qs = qs.filter(printer_id=printer_id)

        return Response({
            'success': True,
            'result': PrinterCategorySerializer(qs, many=True).data,
        })



class PrinterCategoryRemoveView(APIView):
    permission_classes = [IsAuthenticated]
    """DELETE /api/v2/printer-category/{id}/remove/"""

    def delete(self, request, pk):
        try:
            mapping = PrinterCategory.objects.get(pk=pk)
        except PrinterCategory.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Ulash topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        mapping.delete()
        return Response({
            'success': True,
            'message': 'Kategoriya ulashi bekor qilindi',
        })



class PrinterCategoryBulkAssignView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/printer-category/bulk-assign/
    Ko'plab kategoriyalarni printerga ulash (avvalgilar o'chiriladi)"""

    def post(self, request):
        serializer = PrinterCategoryBulkAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        printer_id = serializer.validated_data['printer_id']
        business_id = serializer.validated_data['business_id']
        categories = serializer.validated_data['categories']

        # Avvalgi ulashlarni o'chirish
        PrinterCategory.objects.filter(
            printer_id=printer_id,
            business_id=business_id,
        ).delete()

        # Yangi ulashlar
        mappings = []
        for cat in categories:
            mappings.append(PrinterCategory(
                printer_id=printer_id,
                category_id=cat.get('category_id'),
                category_name=cat.get('category_name', ''),
                business_id=business_id,
            ))

        created = PrinterCategory.objects.bulk_create(mappings)

        return Response({
            'success': True,
            'result': PrinterCategorySerializer(created, many=True).data,
            'message': f'{len(created)} ta kategoriya ulandi',
        })



class PrinterCategoryByPrinterView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/printer-category/by-printer/{printer_id}/"""

    def get(self, request, printer_id):
        mappings = PrinterCategory.objects.filter(
            printer_id=printer_id,
        ).select_related('printer')

        return Response({
            'success': True,
            'result': PrinterCategorySerializer(mappings, many=True).data,
        })


# ============================================================
# PRINTER PRODUCT MAPPING
# ============================================================

