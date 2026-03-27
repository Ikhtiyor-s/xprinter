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


class AgentPollView(APIView):
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = [IsAgentAuthenticated]
    """GET /api/v2/print-job/agent/poll/?business_id=
    Print Agent - pending joblarni olish.
    Agent har 3 soniyada shu endpointga so'rov yuboradi.
    business_id=all bo'lsa — barcha bizneslarning pending joblari qaytariladi."""

    def get(self, request):
        # Agent faqat o'z biznesining joblarini ko'radi
        cred = getattr(request.user, 'credential', None)
        business_id = request.query_params.get('business_id')

        if not business_id:
            return Response({
                'success': False,
                'error': 'business_id parametri kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        # IDOR himoyasi: agent faqat o'z biznesini ko'radi
        if cred and business_id != 'all' and int(business_id) != cred.business_id:
            return Response({'success': False, 'error': "Ruxsat berilmagan"}, status=403)

        if business_id == 'all' and cred:
            # Faqat o'z biznesi
            jobs = PrintJob.objects.filter(
                business_id=cred.business_id,
                status=PrintJob.STATUS_PENDING,
                printer__is_active=True,
            ).select_related('printer').order_by('created_at')
        else:
            jobs = PrintJob.objects.filter(
                business_id=business_id,
                status=PrintJob.STATUS_PENDING,
                printer__is_active=True,
            ).select_related('printer').order_by('created_at')

        result = []
        for job in jobs:
            result.append({
                'id': job.id,
                'order_id': job.order_id,
                'printer_id': job.printer_id,
                'printer_name': job.printer.name,
                'printer_connection': job.printer.connection_type,
                'printer_ip': job.printer.ip_address,
                'printer_port': job.printer.port,
                'printer_usb': job.printer.usb_path,
                'paper_width': job.printer.paper_width,
                'content': job.content,
                'items_data': job.items_data,
                'created_at': job.created_at.isoformat(),
            })

        return Response({
            'success': True,
            'count': len(result),
            'result': result,
        })



class AgentCompleteView(APIView):
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = [IsAgentAuthenticated]
    """POST /api/v2/print-job/agent/complete/
    Print Agent - jobni completed/failed deb belgilash"""

    def post(self, request):
        job_id = request.data.get('job_id')
        job_status = request.data.get('status')  # 'completed' or 'failed'
        error_message = request.data.get('error', '')

        if not job_id or not job_status:
            return Response({
                'success': False,
                'error': 'job_id va status kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            job = PrintJob.objects.get(pk=job_id)
        except PrintJob.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Job topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        if job_status == 'completed':
            job.mark_completed()
        elif job_status == 'failed':
            job.mark_failed(error_message)
            try:
                from .services.notification_service import notify_print_failure
                notify_print_failure(job, error_message)
            except Exception as e:
                logger.error(f"Agent bildirishnoma xatolik: {e}")
        else:
            return Response({
                'success': False,
                'error': 'status faqat "completed" yoki "failed" bo\'lishi mumkin',
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'result': PrintJobSerializer(job).data,
        })


# ============================================================
# NONBOR CONFIG CRUD
# ============================================================


class PrinterAgentSyncView(APIView):
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = [IsAgentAuthenticated]
    """POST /api/v2/printer/agent-sync/
    Agent printer qo'shganda backend bilan sync qiladi.
    Printer yaratadi yoki topadi, mahsulot ulashlarini yangilaydi.
    """
    def post(self, request):
        # Auth is handled by AgentTokenAuthentication
        cred = getattr(request.user, 'credential', None)
        if not cred:
            return Response({'success': False, 'error': 'Auth xato'}, status=401)

        business_id = cred.business_id
        printer_name = request.data.get('name', '').strip()
        if not printer_name:
            return Response({'success': False, 'error': 'Printer nomi kerak'}, status=400)

        product_ids = request.data.get('product_ids', [])
        product_names = request.data.get('product_names', {})  # {"123": "Palov", ...}

        conn_type = request.data.get('connection_type', 'network')
        ip_addr = request.data.get('ip') or None
        port = int(request.data.get('port', 9100))
        usb_path = request.data.get('usb') or None
        paper_width = int(request.data.get('paper_width', 80))
        is_admin = bool(request.data.get('is_admin', False))

        # Printer yaratish yoki topish
        printer, created = Printer.objects.get_or_create(
            business_id=business_id,
            name=printer_name,
            defaults={
                'connection_type': conn_type,
                'ip_address': ip_addr,
                'port': port,
                'usb_path': usb_path,
                'paper_width': paper_width,
                'is_admin': is_admin,
            }
        )

        # Mavjud printer — is_admin yangilash
        if not created:
            printer.is_admin = is_admin
            printer.save(update_fields=['is_admin'])

        # Mahsulot ulashlarini yangilash
        PrinterProduct.objects.filter(printer=printer, business_id=business_id).delete()
        for pid in product_ids:
            pid_int = int(pid)
            pname = product_names.get(str(pid), '') or product_names.get(pid, '')
            PrinterProduct.objects.update_or_create(
                product_id=pid_int,
                business_id=business_id,
                defaults={
                    'printer': printer,
                    'product_name': pname,
                },
            )

        return Response({
            'success': True,
            'printer_id': printer.id,
            'created': created,
            'products_assigned': len(product_ids),
        })


# ============================================================
# AGENT CREDENTIAL CRUD (Print Agent login/parol boshqaruvi)
# ============================================================

