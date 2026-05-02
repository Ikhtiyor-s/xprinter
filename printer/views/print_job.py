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


class PrintJobListView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """GET /api/v2/print-job/list/?business_id=&status=&printer_id=&order_id="""

    def get(self, request):
        business_id = request.query_params.get('business_id')
        if not business_id:
            return Response({
                'success': False,
                'error': 'business_id parametri kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        qs = PrintJob.objects.filter(
            business_id=business_id,
        ).select_related('printer')

        # Filterlar
        job_status = request.query_params.get('status')
        printer_id = request.query_params.get('printer_id')
        order_id = request.query_params.get('order_id')

        if job_status:
            qs = qs.filter(status=job_status)
        if printer_id:
            qs = qs.filter(printer_id=printer_id)
        if order_id:
            qs = qs.filter(order_id=order_id)

        # Oxirgi 100 ta
        qs = qs[:100]

        return Response({
            'success': True,
            'result': PrintJobSerializer(qs, many=True).data,
        })



class PrintJobRetryView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """POST /api/v2/print-job/{id}/retry/ - Qayta chop etish"""

    def post(self, request, pk):
        try:
            job = PrintJob.objects.select_related('printer').get(pk=pk)
        except PrintJob.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Print job topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        if not job.can_retry:
            return Response({
                'success': False,
                'error': f'Qayta urinishlar tugadi ({job.retry_count}/{job.max_retries})',
            }, status=status.HTTP_400_BAD_REQUEST)

        success, error = retry_print_job(job)

        if success:
            return Response({
                'success': True,
                'message': 'Qayta chop etildi',
                'result': PrintJobSerializer(job).data,
            })
        else:
            return Response({
                'success': False,
                'error': error,
                'result': PrintJobSerializer(job).data,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class PrintOrderView(APIView):
    permission_classes = [XprinterApiKeyPermission]
    """POST /api/v2/print-job/print-order/{order_id}/
    Buyurtmani qo'lda chop etish (manual trigger)"""

    def post(self, request, order_id):
        serializer = PrintOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        data['order_id'] = order_id

        order_data = {
            'order_id': order_id,
            'order_number': data.get('order_number', str(order_id)),
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

        jobs = print_order(
            order_data=order_data,
            items=data['items'],
            business_id=data['business_id'],
        )

        completed = sum(1 for j in jobs if j.status == PrintJob.STATUS_COMPLETED)
        failed = sum(1 for j in jobs if j.status == PrintJob.STATUS_FAILED)

        return Response({
            'success': True,
            'message': f'{completed} ta printerga chop etildi, {failed} ta xatolik',
            'result': PrintJobSerializer(jobs, many=True).data,
        })


