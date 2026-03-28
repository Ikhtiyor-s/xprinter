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


class PrinterDetectView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/printer/detect/ - Tizimda mavjud printerlarni aniqlash"""

    def get(self, request):
        printers = detect_system_printers()
        return Response({
            'success': True,
            'count': len(printers),
            'printers': printers,
        })



class PrinterCreateView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/printer/create/ - Yangi printer qo'shish"""

    def post(self, request):
        serializer = PrinterCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        printer = serializer.save()
        return Response({
            'success': True,
            'result': PrinterDetailSerializer(printer).data,
        }, status=status.HTTP_201_CREATED)



class PrinterListView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/printer/list/?business_id= - Printerlar ro'yxati"""

    def get(self, request):
        biz_id, err = enforce_business_id(request)
        if err:
            return err
        if not biz_id:
            return Response({'success': False, 'error': 'business_id kerak'}, status=400)

        from django.db.models import Count
        printers = Printer.objects.filter(business_id=biz_id).annotate(
            categories_count=Count('categories', distinct=True),
            products_count=Count('products', distinct=True),
        )
        return Response({
            'success': True,
            'result': PrinterListSerializer(printers, many=True).data,
        })



class PrinterDetailView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/printer/{id}/detail/ - Printer batafsil"""

    def get(self, request, pk):
        try:
            printer = Printer.objects.prefetch_related('categories', 'products').get(pk=pk)
        except Printer.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Printer topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'success': True,
            'result': PrinterDetailSerializer(printer).data,
        })



class PrinterUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    """PUT /api/v2/printer/{id}/update/ - Printerni tahrirlash"""

    def put(self, request, pk):
        try:
            printer = Printer.objects.get(pk=pk)
        except Printer.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Printer topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = PrinterUpdateSerializer(printer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        printer = serializer.save()
        return Response({
            'success': True,
            'result': PrinterDetailSerializer(printer).data,
        })

    patch = put



class PrinterDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    """DELETE /api/v2/printer/{id}/delete/ - Printerni o'chirish"""

    def delete(self, request, pk):
        try:
            printer = Printer.objects.get(pk=pk)
        except Printer.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Printer topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        printer.delete()
        return Response({
            'success': True,
            'message': 'Printer o\'chirildi',
        })



class PrinterTestPrintView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/printer/{id}/test-print/ - Test sahifa chop etish"""

    def post(self, request, pk):
        try:
            printer = Printer.objects.get(pk=pk)
        except Printer.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Printer topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        success, error = send_test_print(printer)

        if success:
            return Response({
                'success': True,
                'message': f'Test sahifa {printer.name} ga yuborildi',
            })
        else:
            return Response({
                'success': False,
                'error': error,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# PRINTER CATEGORY MAPPING
# ============================================================

