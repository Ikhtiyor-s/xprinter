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


class PrinterProductAssignView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """POST /api/v2/printer-product/assign/ - Mahsulotni printerga ulash"""

    def post(self, request):
        serializer = PrinterProductAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        mapping = PrinterProduct.objects.create(
            printer_id=serializer.validated_data['printer_id'],
            product_id=serializer.validated_data['product_id'],
            product_name=serializer.validated_data.get('product_name', ''),
            business_id=serializer.validated_data['business_id'],
        )

        return Response({
            'success': True,
            'result': PrinterProductSerializer(mapping).data,
        }, status=status.HTTP_201_CREATED)



class PrinterProductListView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """GET /api/v2/printer-product/list/?business_id=&printer_id="""

    def get(self, request):
        business_id = request.query_params.get('business_id')
        printer_id = request.query_params.get('printer_id')

        if not business_id:
            return Response({
                'success': False,
                'error': 'business_id parametri kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        qs = PrinterProduct.objects.filter(
            business_id=business_id,
        ).select_related('printer')

        if printer_id:
            qs = qs.filter(printer_id=printer_id)

        return Response({
            'success': True,
            'result': PrinterProductSerializer(qs, many=True).data,
        })



class PrinterProductRemoveView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """DELETE /api/v2/printer-product/{id}/remove/"""

    def delete(self, request, pk):
        try:
            mapping = PrinterProduct.objects.get(pk=pk)
        except PrinterProduct.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Ulash topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        mapping.delete()
        return Response({
            'success': True,
            'message': 'Mahsulot ulashi bekor qilindi',
        })



class PrinterProductBulkAssignView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """POST /api/v2/printer-product/bulk-assign/
    Ko'plab mahsulotlarni printerga ulash (shu printerdagi avvalgilar o'chiriladi)"""

    def post(self, request):
        serializer = PrinterProductBulkAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        printer_id = serializer.validated_data['printer_id']
        business_id = serializer.validated_data['business_id']
        products = serializer.validated_data['products']

        # Shu printerdagi avvalgi ulashlarni o'chirish
        PrinterProduct.objects.filter(
            printer_id=printer_id,
            business_id=business_id,
        ).delete()

        # Yangi ulashlar
        mappings = []
        for prod in products:
            mappings.append(PrinterProduct(
                printer_id=printer_id,
                product_id=prod.get('product_id'),
                product_name=prod.get('product_name', ''),
                business_id=business_id,
            ))

        created = PrinterProduct.objects.bulk_create(mappings)

        return Response({
            'success': True,
            'result': PrinterProductSerializer(created, many=True).data,
            'message': f'{len(created)} ta mahsulot ulandi',
        })



class PrinterProductByPrinterView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """GET /api/v2/printer-product/by-printer/{printer_id}/"""

    def get(self, request, printer_id):
        mappings = PrinterProduct.objects.filter(
            printer_id=printer_id,
        ).select_related('printer')

        return Response({
            'success': True,
            'result': PrinterProductSerializer(mappings, many=True).data,
        })


# ============================================================
# PRINT JOB
# ============================================================

