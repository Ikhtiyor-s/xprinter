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


# ─── Admin.nonbor ga print natijasini yuborish ────────────────────────────────

def _notify_admin_printed(order_id, business_id, jobs):
    """Chek chiqarilgandan keyin admin.nonbor ga natija yuborish.

    POST {api_url}/api/webhook/xprinter
    Headers: X-Webhook-Secret: {api_secret}
    """
    import threading
    import requests as _req

    config = NonborConfig.objects.filter(business_id=business_id, is_active=True).first()
    if not config or not config.api_url:
        return

    # api_url: "https://prod.nonbor.uz/api/v2" → base: "https://prod.nonbor.uz"
    base_url = config.api_url.rstrip('/').removesuffix('/api/v2').removesuffix('/api')
    callback_url = f"{base_url}/api/webhook/xprinter"

    completed = [j for j in jobs if j.status == PrintJob.STATUS_COMPLETED]
    failed = [j for j in jobs if j.status == PrintJob.STATUS_FAILED]
    pending = [j for j in jobs if j.status == PrintJob.STATUS_PENDING]

    if completed:
        print_status = "printed"
    elif failed and not completed and not pending:
        print_status = "failed"
    else:
        print_status = "partial"

    printer_names = []
    for j in jobs:
        try:
            name = j.printer.name
            if name not in printer_names:
                printer_names.append(name)
        except Exception:
            pass

    payload = {
        "event": "print.status",
        "data": {
            "job_id":      str(jobs[0].id) if jobs else "",
            "order_id":    order_id,
            "business_id": business_id,
            "status":      print_status,
            "printers":    printer_names,
        },
    }

    headers = {"Content-Type": "application/json"}
    if config.api_secret:
        headers["X-Webhook-Secret"] = config.api_secret

    def _send():
        try:
            r = _req.post(callback_url, json=payload, headers=headers, timeout=8)
            logger.info(f"[Webhook] Admin callback → {callback_url}: {r.status_code}")
        except Exception as e:
            logger.debug(f"[Webhook] Admin callback xato (davom etadi): {e}")

    threading.Thread(target=_send, daemon=True).start()


# ─── Yangi format payload ni normalize qilish ─────────────────────────────────

def _parse_webhook_payload(data: dict) -> dict:
    """
    Yangi format (event: "order:new") va eski format (state: "ACCEPTED") ni qo'llab-quvvatlash.
    Natijada normalize qilingan order_data va items qaytaradi.
    """
    # Yangi format field nomlari → eski field nomlari
    order_data = {
        'order_id':        str(data.get('order_id') or data.get('orderId', '')),
        'order_number':    str(data.get('order_number') or data.get('order_id', '')),
        'business_name':   data.get('business_name', ''),
        'customer_name':   (
            data.get('client_name') or           # yangi format
            data.get('customer_name', '')         # eski format
        ),
        'customer_phone':  (
            data.get('client_phone') or
            data.get('customer_phone', '')
        ),
        'customer_address': (
            data.get('delivery_address') or
            data.get('customer_address', '')
        ),
        'delivery_method': (
            data.get('delivery_type') or          # yangi format
            data.get('delivery_method', '')        # eski format
        ),
        'payment_method':  (
            data.get('payment_type') or           # yangi format
            data.get('payment_method', '')         # eski format
        ),
        'comment':         data.get('comment', ''),
        'total_price':     float(data.get('total_price') or 0),
        'scheduled_time':  data.get('scheduled_time', ''),
        'order_type':      data.get('order_type', ''),
    }
    items = data.get('items', [])
    return order_data, items


# ============================================================
# PRINTER CRUD
# ============================================================


@method_decorator(csrf_exempt, name='dispatch')
class PrintWebhookView(APIView):
    authentication_classes = [WebhookAuthentication]
    permission_classes = [IsWebhookAuthenticated]
    """POST /api/v2/print-job/webhook/
    Nonbor backenddan webhook — yangi buyurtma kelganda avtomatik chop etish.

    Qo'llab-quvvatlangan formatlar:
    1. Yangi format: { event: "order:new", client_name, delivery_type, payment_type, ... }
    2. Eski format:  { state: "ACCEPTED", customer_name, delivery_method, payment_method, ... }
    """

    def post(self, request):
        data = request.data

        # ── Filtrlash ────────────────────────────────────────────────

        # Yangi format: event=order:new tekshirish
        event = data.get('event', '')
        if event and event not in ('order:new', 'order.new', 'order_new'):
            return Response({
                'success': True,
                'message': f'Event "{event}" — chop etish kerak emas',
                'printed': False,
            })

        # To'lanmagan buyurtmalar (yangi va eski format)
        payment_type = (
            data.get('payment_type') or
            data.get('payment_method') or ''
        ).upper()
        if payment_type in ('WAITING_PAYMENT', 'UNPAID'):
            return Response({
                'success': True,
                'message': f'To\'lov turi {payment_type} — chop etilmaydi',
                'printed': False,
            })

        # Eski format: state tekshirish
        state = data.get('state', '')
        if state:
            skip_states = {'CANCELLED', 'PENDING', 'WAITING_PAYMENT', 'PAYMENT_EXPIRED'}
            if state.upper() in skip_states:
                return Response({
                    'success': True,
                    'message': f'Status {state} — chop etish kerak emas',
                    'printed': False,
                })

        # ── business_id olish ────────────────────────────────────────
        business_id = data.get('business_id')
        if not business_id:
            return Response(
                {'success': False, 'error': 'business_id kiritilmagan'},
                status=400,
            )
        try:
            business_id = int(business_id)
        except (TypeError, ValueError):
            return Response(
                {'success': False, 'error': 'business_id noto\'g\'ri'},
                status=400,
            )

        # ── Avtomatik chop etish yoqilgan printerlar bormi? ──────────
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

        # ── Payload parse ────────────────────────────────────────────
        order_data, items = _parse_webhook_payload(data)

        if not items:
            logger.warning(f"Webhook: order #{order_data['order_id']} items bo'sh")
            return Response({
                'success': True,
                'message': 'Buyurtmada taomlar yo\'q',
                'printed': False,
            })

        # ── Items format normalize ───────────────────────────────────
        normalized_items = []
        for item in items:
            normalized_items.append({
                'name':        item.get('name') or item.get('product_name', ''),
                'quantity':    item.get('quantity', 1),
                'price':       item.get('price', 0),
                'product_id':  item.get('id') or item.get('product_id'),
                'category_id': item.get('category_id'),
                'category_name': item.get('category') or item.get('category_name', ''),
            })

        # ── Chop etish ───────────────────────────────────────────────
        jobs = print_order(
            order_data=order_data,
            items=normalized_items,
            business_id=business_id,
        )

        completed = sum(1 for j in jobs if j.status == PrintJob.STATUS_COMPLETED)
        failed = sum(1 for j in jobs if j.status == PrintJob.STATUS_FAILED)

        logger.info(
            f"Webhook: order #{order_data['order_id']} → "
            f"{completed} chop etildi, {failed} xatolik"
        )

        # ── Admin.nonbor ga callback ─────────────────────────────────
        if jobs:
            _notify_admin_printed(order_data['order_id'], business_id, jobs)

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
