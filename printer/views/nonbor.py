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


class NonborConfigCreateView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/nonbor-config/create/ - Nonbor API sozlamasi yaratish"""

    def post(self, request):
        biz_id, err = enforce_business_id(request)
        if err:
            return err
        if biz_id and int(request.data.get('business_id', 0)) != biz_id:
            return Response({'success': False, 'error': 'Bu biznesga ruxsat berilmagan'}, status=403)
        serializer = NonborConfigCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()

        # Biznes nomini avtomatik olishga harakat
        try:
            api = NonborAPI(config)
            info = api.get_business_info()
            if info:
                biz_name = info.get('title') or info.get('name', '')
                if biz_name:
                    config.business_name = biz_name
                    config.save(update_fields=['business_name'])
        except Exception:
            pass

        return Response({
            'success': True,
            'result': NonborConfigSerializer(config).data,
        }, status=status.HTTP_201_CREATED)



class NonborConfigListView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/nonbor-config/list/ - Nonbor sozlamalari"""

    def get(self, request):
        biz_id, err = enforce_business_id(request)
        if err:
            return err
        configs = NonborConfig.objects.all()
        if biz_id:
            configs = configs.filter(business_id=biz_id).order_by('-created_at')
        return Response({
            'success': True,
            'result': NonborConfigSerializer(configs, many=True).data,
        })



class NonborConfigDetailView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/nonbor-config/{business_id}/detail/"""

    def get(self, request, business_id):
        seller_biz = get_seller_business_id(request.user)
        if seller_biz and seller_biz != business_id:
            return Response({'success': False, 'error': 'Ruxsat berilmagan'}, status=403)
        try:
            config = NonborConfig.objects.get(business_id=business_id)
        except NonborConfig.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Nonbor sozlamasi topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'success': True,
            'result': NonborConfigSerializer(config).data,
        })



class NonborConfigUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    """PUT /api/v2/nonbor-config/{business_id}/update/"""

    def put(self, request, business_id):
        seller_biz = get_seller_business_id(request.user)
        if seller_biz and seller_biz != business_id:
            return Response({'success': False, 'error': 'Ruxsat berilmagan'}, status=403)
        try:
            config = NonborConfig.objects.get(business_id=business_id)
        except NonborConfig.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Nonbor sozlamasi topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = NonborConfigUpdateSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        return Response({
            'success': True,
            'result': NonborConfigSerializer(config).data,
        })

    patch = put



class NonborConfigDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    """DELETE /api/v2/nonbor-config/{business_id}/delete/"""

    def delete(self, request, business_id):
        seller_biz = get_seller_business_id(request.user)
        if seller_biz and seller_biz != business_id:
            return Response({'success': False, 'error': 'Ruxsat berilmagan'}, status=403)
        try:
            config = NonborConfig.objects.get(business_id=business_id)
        except NonborConfig.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Nonbor sozlamasi topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        config.delete()
        return Response({
            'success': True,
            'message': 'Nonbor sozlamasi o\'chirildi',
        })


# ============================================================
# NONBOR POLLING
# ============================================================


class NonborPollView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/nonbor/poll/{business_id}/
    Nonbor API dan yangi buyurtmalarni olib, chop etish.
    Frontend yoki cron bu endpointni chaqiradi."""

    def post(self, request, business_id):
        try:
            config = NonborConfig.objects.get(
                business_id=business_id,
                is_active=True,
            )
        except NonborConfig.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Nonbor sozlamasi topilmadi yoki o\'chirilgan',
            }, status=status.HTTP_404_NOT_FOUND)

        new_count, printed, errors = poll_and_print(config)

        return Response({
            'success': True,
            'new_orders': new_count,
            'printed': printed,
            'errors': errors,
            'last_poll_at': config.last_poll_at.isoformat() if config.last_poll_at else None,
        })



class NonborOrdersView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/nonbor/orders/{business_id}/
    Nonbor API dan hozirgi buyurtmalarni ko'rish (chop etmasdan)"""

    def get(self, request, business_id):
        try:
            config = NonborConfig.objects.get(
                business_id=business_id,
                is_active=True,
            )
        except NonborConfig.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Nonbor sozlamasi topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        api = NonborAPI(config)
        orders = api.get_orders()

        return Response({
            'success': True,
            'count': len(orders),
            'result': orders,
        })



class NonborPollStartView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/nonbor/poll-start/{business_id}/
    Avtomatik pollingni yoqish"""

    def post(self, request, business_id):
        try:
            config = NonborConfig.objects.get(business_id=business_id)
        except NonborConfig.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Nonbor sozlamasi topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        config.poll_enabled = True
        config.save(update_fields=['poll_enabled'])
        return Response({
            'success': True,
            'message': 'Avtomatik polling yoqildi',
            'result': NonborConfigSerializer(config).data,
        })



class NonborPollStopView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/nonbor/poll-stop/{business_id}/
    Avtomatik pollingni o'chirish"""

    def post(self, request, business_id):
        try:
            config = NonborConfig.objects.get(business_id=business_id)
        except NonborConfig.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Nonbor sozlamasi topilmadi',
            }, status=status.HTTP_404_NOT_FOUND)

        config.poll_enabled = False
        config.save(update_fields=['poll_enabled'])
        return Response({
            'success': True,
            'message': 'Avtomatik polling o\'chirildi',
            'result': NonborConfigSerializer(config).data,
        })



class NonborPollAllView(APIView):
    permission_classes = [IsAuthenticated]
    """POST /api/v2/nonbor/poll-all/
    Barcha aktiv bizneslarni bir vaqtda Nonbor API dan polling qilish.
    Agent shu endpointni chaqiradi — har bir biznes uchun alohida poll_and_print."""

    def post(self, request):
        # Faqat aktiv, poll_enabled va printerli bizneslar
        from printer.models import Printer as PrinterModel
        biz_with_printers = set(
            PrinterModel.objects.filter(is_active=True)
            .values_list('business_id', flat=True)
            .distinct()
        )

        configs = NonborConfig.objects.filter(
            is_active=True,
            poll_enabled=True,
            business_id__in=biz_with_printers,
        )

        results = []
        total_new = 0
        total_printed = 0
        total_errors = 0

        # 1) Nonbor API dan polling (mavjud logika)
        for config in configs:
            try:
                new_count, printed, errors = poll_and_print(config)
                total_new += new_count
                total_printed += printed
                total_errors += errors
                if new_count > 0:
                    results.append({
                        'business_id': config.business_id,
                        'business_name': config.business_name,
                        'source': 'nonbor',
                        'new_orders': new_count,
                        'printed': printed,
                        'errors': errors,
                    })
            except Exception as e:
                logger.error(f"Poll-all xato BIZ={config.business_id}: {e}")
                total_errors += 1
                results.append({
                    'business_id': config.business_id,
                    'business_name': config.business_name,
                    'source': 'nonbor',
                    'error': str(e),
                })

        # 2) Tashqi tizimlardan polling (Telegram, Yandex, Uzum, Express24, iiko va h.k.)
        from printer.services.nonbor_api import poll_and_print_service
        from printer.models import OrderService as OrderServiceModel

        ext_services = OrderServiceModel.objects.filter(
            is_active=True,
            poll_enabled=True,
            business_id__in=biz_with_printers,
        ).exclude(api_url='')

        for svc in ext_services:
            try:
                new_count, printed, errors = poll_and_print_service(svc)
                total_new += new_count
                total_printed += printed
                total_errors += errors
                if new_count > 0:
                    results.append({
                        'business_id': svc.business_id,
                        'business_name': svc.business_name,
                        'source': svc.service_name,
                        'new_orders': new_count,
                        'printed': printed,
                        'errors': errors,
                    })
            except Exception as e:
                logger.error(f"Poll-all OrderService #{svc.id} xato: {e}")
                total_errors += 1
                results.append({
                    'business_id': svc.business_id,
                    'business_name': svc.business_name,
                    'source': svc.service_name,
                    'error': str(e),
                })

        if not results and not configs.exists() and not ext_services.exists():
            return Response({
                'success': True,
                'message': 'Aktiv bizneslar topilmadi',
                'results': [],
            })

        return Response({
            'success': True,
            'total_new': total_new,
            'total_printed': total_printed,
            'total_errors': total_errors,
            'results': results,
        })
