import logging
import os
import time as _time

from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

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
    """GET /api/v2/printer/detect/ - Tizimda mavjud printerlarni aniqlash"""

    def get(self, request):
        printers = detect_system_printers()
        return Response({
            'success': True,
            'count': len(printers),
            'printers': printers,
        })


class PrinterCreateView(APIView):
    """POST /api/v2/printer/create/ - Yangi printer qo'shish"""
    pass  # no explicit permission, uses global AllowAny

    def post(self, request):
        serializer = PrinterCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        printer = serializer.save()
        return Response({
            'success': True,
            'result': PrinterDetailSerializer(printer).data,
        }, status=status.HTTP_201_CREATED)


class PrinterListView(APIView):
    """GET /api/v2/printer/list/?business_id= - Printerlar ro'yxati"""
    pass  # no explicit permission, uses global AllowAny

    def get(self, request):
        business_id = request.query_params.get('business_id')
        if not business_id:
            return Response({
                'success': False,
                'error': 'business_id parametri kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        printers = Printer.objects.filter(business_id=business_id)
        return Response({
            'success': True,
            'result': PrinterListSerializer(printers, many=True).data,
        })


class PrinterDetailView(APIView):
    """GET /api/v2/printer/{id}/detail/ - Printer batafsil"""
    pass  # no explicit permission, uses global AllowAny

    def get(self, request, pk):
        try:
            printer = Printer.objects.get(pk=pk)
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
    """PUT /api/v2/printer/{id}/update/ - Printerni tahrirlash"""
    pass  # no explicit permission, uses global AllowAny

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
    """DELETE /api/v2/printer/{id}/delete/ - Printerni o'chirish"""
    pass  # no explicit permission, uses global AllowAny

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
    """POST /api/v2/printer/{id}/test-print/ - Test sahifa chop etish"""
    pass  # no explicit permission, uses global AllowAny

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

class PrinterCategoryAssignView(APIView):
    """POST /api/v2/printer-category/assign/ - Kategoriyani printerga ulash"""
    pass  # no explicit permission, uses global AllowAny

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
    """GET /api/v2/printer-category/list/?business_id=&printer_id="""
    pass  # no explicit permission, uses global AllowAny

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
    """DELETE /api/v2/printer-category/{id}/remove/"""
    pass  # no explicit permission, uses global AllowAny

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
    """POST /api/v2/printer-category/bulk-assign/
    Ko'plab kategoriyalarni printerga ulash (avvalgilar o'chiriladi)"""
    pass  # no explicit permission, uses global AllowAny

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
    """GET /api/v2/printer-category/by-printer/{printer_id}/"""
    pass  # no explicit permission, uses global AllowAny

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

class PrinterProductAssignView(APIView):
    """POST /api/v2/printer-product/assign/ - Mahsulotni printerga ulash"""
    pass  # no explicit permission, uses global AllowAny

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
    """GET /api/v2/printer-product/list/?business_id=&printer_id="""
    pass  # no explicit permission, uses global AllowAny

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
    """DELETE /api/v2/printer-product/{id}/remove/"""
    pass  # no explicit permission, uses global AllowAny

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
    """POST /api/v2/printer-product/bulk-assign/
    Ko'plab mahsulotlarni printerga ulash (shu printerdagi avvalgilar o'chiriladi)"""
    pass  # no explicit permission, uses global AllowAny

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
    """GET /api/v2/printer-product/by-printer/{printer_id}/"""
    pass  # no explicit permission, uses global AllowAny

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

class PrintJobListView(APIView):
    """GET /api/v2/print-job/list/?business_id=&status=&printer_id=&order_id="""
    pass  # no explicit permission, uses global AllowAny

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
    """POST /api/v2/print-job/{id}/retry/ - Qayta chop etish"""
    pass  # no explicit permission, uses global AllowAny

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
    """POST /api/v2/print-job/print-order/{order_id}/
    Buyurtmani qo'lda chop etish (manual trigger)"""
    pass  # no explicit permission, uses global AllowAny

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


class AgentPollView(APIView):
    """GET /api/v2/print-job/agent/poll/?business_id=
    Print Agent - pending joblarni olish.
    Agent har 3 soniyada shu endpointga so'rov yuboradi.
    business_id=all bo'lsa — barcha bizneslarning pending joblari qaytariladi."""
    pass  # no explicit permission, uses global AllowAny

    def get(self, request):
        business_id = request.query_params.get('business_id')
        if not business_id:
            return Response({
                'success': False,
                'error': 'business_id parametri kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        # business_id=all — barcha bizneslar uchun pending joblar
        if business_id == 'all':
            jobs = PrintJob.objects.filter(
                status=PrintJob.STATUS_PENDING,
                printer__is_active=True,
            ).select_related('printer').order_by('created_at')
        else:
            # Faqat bitta biznes uchun pending joblar
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
    """POST /api/v2/print-job/agent/complete/
    Print Agent - jobni completed/failed deb belgilash"""
    pass  # no explicit permission, uses global AllowAny

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

class NonborConfigCreateView(APIView):
    """POST /api/v2/nonbor-config/create/ - Nonbor API sozlamasi yaratish"""
    pass  # no explicit permission, uses global AllowAny

    def post(self, request):
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
    """GET /api/v2/nonbor-config/list/ - Barcha Nonbor sozlamalari"""
    pass  # no explicit permission, uses global AllowAny

    def get(self, request):
        configs = NonborConfig.objects.all().order_by('-created_at')
        return Response({
            'success': True,
            'result': NonborConfigSerializer(configs, many=True).data,
        })


class NonborConfigDetailView(APIView):
    """GET /api/v2/nonbor-config/{business_id}/detail/"""
    pass  # no explicit permission, uses global AllowAny

    def get(self, request, business_id):
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
    """PUT /api/v2/nonbor-config/{business_id}/update/"""
    pass  # no explicit permission, uses global AllowAny

    def put(self, request, business_id):
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
    """DELETE /api/v2/nonbor-config/{business_id}/delete/"""
    pass  # no explicit permission, uses global AllowAny

    def delete(self, request, business_id):
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
    """POST /api/v2/nonbor/poll/{business_id}/
    Nonbor API dan yangi buyurtmalarni olib, chop etish.
    Frontend yoki cron bu endpointni chaqiradi."""
    pass  # no explicit permission, uses global AllowAny

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
    """GET /api/v2/nonbor/orders/{business_id}/
    Nonbor API dan hozirgi buyurtmalarni ko'rish (chop etmasdan)"""
    pass  # no explicit permission, uses global AllowAny

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
    """POST /api/v2/nonbor/poll-start/{business_id}/
    Avtomatik pollingni yoqish"""
    pass  # no explicit permission, uses global AllowAny

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
    """POST /api/v2/nonbor/poll-stop/{business_id}/
    Avtomatik pollingni o'chirish"""
    pass  # no explicit permission, uses global AllowAny

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
    """POST /api/v2/nonbor/poll-all/
    Barcha aktiv bizneslarni bir vaqtda Nonbor API dan polling qilish.
    Agent shu endpointni chaqiradi — har bir biznes uchun alohida poll_and_print."""
    pass

    def post(self, request):
        # Faqat aktiv, poll_enabled va printerli bizneslar
        from .models import Printer as PrinterModel
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
        from .services.nonbor_api import poll_and_print_service
        from .models import OrderService as OrderServiceModel

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


class PrintWebhookView(APIView):
    """POST /api/v2/print-job/webhook/
    Nonbor backenddan webhook - buyurtma statusi o'zgarganda avtomatik chop etish"""
    permission_classes = []  # Webhook - autentifikatsiyasiz (secret bilan)

    def post(self, request):
        # Webhook secret tekshirish
        webhook_secret = request.headers.get('X-Webhook-Secret', '')
        expected = os.environ.get('WEBHOOK_SECRET', 'nonbor-webhook-secret')
        if webhook_secret != expected:
            return Response({'error': 'Invalid webhook secret'}, status=403)

        serializer = WebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        state = data.get('state', '')

        # Faqat ACCEPTED statusda avtomatik chop etish
        if state != 'ACCEPTED':
            return Response({
                'success': True,
                'message': f'Status {state} - chop etish kerak emas',
                'printed': False,
            })

        business_id = data['business_id']

        # Avtomatik chop etish yoqilgan printerlar bormi?
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

        order_data = {
            'order_id': data['order_id'],
            'order_number': data.get('order_number', str(data['order_id'])),
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

        items = data.get('items', [])
        if not items:
            logger.warning(f"Webhook: order #{data['order_id']} items bo'sh")
            return Response({
                'success': True,
                'message': 'Buyurtmada taomlar yo\'q',
                'printed': False,
            })

        jobs = print_order(
            order_data=order_data,
            items=items,
            business_id=business_id,
        )

        completed = sum(1 for j in jobs if j.status == PrintJob.STATUS_COMPLETED)
        failed = sum(1 for j in jobs if j.status == PrintJob.STATUS_FAILED)

        logger.info(
            f"Webhook: order #{data['order_id']} → "
            f"{completed} chop etildi, {failed} xatolik"
        )

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

class AgentAuthView(APIView):
    """POST /api/v2/agent/auth/
    Print Agent uchun autentifikatsiya.
    Admin har bir biznesga alohida login/parol beradi.
    {username, password} → {business_id, business_name}"""
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '').strip()

        if not username or not password:
            return Response({
                'success': False,
                'error': 'Login va parol kiritilmagan',
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            cred = AgentCredential.objects.get(username=username, is_active=True)
        except AgentCredential.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Login topilmadi yoki bloklangan',
            }, status=status.HTTP_401_UNAUTHORIZED)

        if not cred.check_password(password):
            return Response({
                'success': False,
                'error': 'Parol noto\'g\'ri',
            }, status=status.HTTP_401_UNAUTHORIZED)

        return Response({
            'success': True,
            'business_id': cred.business_id,
            'business_name': cred.business_name,
            'username': cred.username,
        })


# Mahsulotlar keshi: {business_id: (timestamp, products_list)}
_MENU_CACHE = {}
_MENU_CACHE_TTL = 3600  # 1 soat


class NonborMenuView(APIView):
    """GET /api/v2/nonbor/menu/<business_id>/
    Agent uchun: biznes mahsulotlar ro'yxatini olish (Nonbor API proxy)
    Auth: ?username=...&password=...
    """
    def get(self, request, business_id):
        username = request.GET.get('username', '').strip()
        password = request.GET.get('password', '').strip()
        force_refresh = request.GET.get('refresh', '').strip() == '1'

        # Agent autentifikatsiya
        try:
            cred = AgentCredential.objects.get(username=username, is_active=True)
        except AgentCredential.DoesNotExist:
            return Response({'success': False, 'error': 'Login topilmadi'}, status=401)
        if not cred.check_password(password) or cred.business_id != business_id:
            return Response({'success': False, 'error': 'Auth xato'}, status=401)

        # Keshdan qaytarish (agar yangi so'rov emas bo'lsa)
        cached = _MENU_CACHE.get(business_id)
        if cached and not force_refresh:
            ts, cached_products = cached
            if _time.time() - ts < _MENU_CACHE_TTL:
                return Response({'success': True, 'count': len(cached_products), 'products': cached_products})

        # Nonbor config: faqat shu biznes uchun
        config = NonborConfig.objects.filter(business_id=business_id, is_active=True).first()
        if not config:
            # Avtomatik yaratish: default sozlamalar bilan
            default_config = NonborConfig.objects.filter(is_active=True).first()
            if default_config:
                config = NonborConfig.objects.create(
                    business_id=business_id,
                    business_name=cred.business_name or f'Biznes #{business_id}',
                    api_url=default_config.api_url,
                    api_secret=default_config.api_secret,
                    is_active=True,
                )
            else:
                return Response({
                    'success': False,
                    'error': 'Nonbor API sozlamasi topilmadi. Admin "Nonbor API" tabida sozlash kerak.',
                }, status=404)

        # Nonbor API dan mahsulotlar
        # products/?business=<id> — barcha mahsulotlar (menu_categoriyasiz ham)
        # products-by-category/ faqat menu_category ga biriktirilganlarni qaytaradi
        api = NonborAPI(config)
        all_raw = []
        page = 1
        while True:
            data = api._get(
                'products/',
                params={'business': business_id, 'page': page, 'page_size': 100}
            )
            if not data:
                break
            result = data.get('result', data) if isinstance(data, dict) else data
            if isinstance(result, dict):
                result = result.get('results', [])
            if not result:
                break
            all_raw.extend(result)
            if len(result) < 100:
                break
            page += 1

        # bo'sh bo'lsa products-by-category/ ga fallback
        if not all_raw:
            page = 1
            while True:
                data = api._get(
                    f'business/{business_id}/products-by-category/',
                    params={'page': page, 'page_size': 100}
                )
                if not data:
                    break
                result = data.get('result', []) if isinstance(data, dict) else data
                if isinstance(result, dict):
                    result = result.get('results', [])
                if not result:
                    break
                all_raw.extend(result)
                if len(result) < 100:
                    break
                page += 1

        products = []
        seen_ids = set()
        for p in all_raw:
            pid = p.get('id')
            if pid in seen_ids:
                continue
            # Faqat shu biznesga tegishli mahsulotlar
            p_biz = p.get('business')
            if isinstance(p_biz, dict):
                p_biz_id = p_biz.get('id')
            elif isinstance(p_biz, (int, str)):
                p_biz_id = int(p_biz) if str(p_biz).isdigit() else None
            else:
                p_biz_id = None
            if p_biz_id is not None and p_biz_id != business_id:
                continue
            seen_ids.add(pid)
            mc = p.get('menu_category') or {}
            cat = p.get('category') or {}
            # Kategoriya nomi: menu_category ustun, bo'lmasa category
            # Encoding xatosi bo'lgan (garbled) nomlar uchun category.name ga fallback
            mc_name = mc.get('name', '') or ''
            cat_name_raw = cat.get('name', '') or ''
            # Agar mc_name o'qilishi qiyin (lot of non-latin/non-uzbek) bo'lsa,
            # latin-1 → utf-8 decode urinib ko'r, aks holda category.name ishlatamiz
            def _safe_cat(s, fallback):
                if not s:
                    return fallback or 'Boshqa'
                # Faqat ASCII + O'zbek/Ruscha harflar bo'lsa yaxshi
                printable = sum(1 for c in s if c.isalpha() and ord(c) < 0x500)
                total = len(s)
                if total > 0 and printable / total < 0.5:
                    # Garbled — latin-1→utf-8 urinib ko'r
                    try:
                        fixed = s.encode('latin-1').decode('utf-8')
                        return fixed
                    except Exception:
                        return fallback or 'Boshqa'
                return s
            cat_name = _safe_cat(mc_name, cat_name_raw) or cat_name_raw or 'Boshqa'
            products.append({
                'id': pid,
                'name': p.get('name') or p.get('title', ''),
                'category_id': mc.get('id') or cat.get('id'),
                'category_name': cat_name,
            })

        # Nonbor API javob bermasa va keshda bor bo'lsa — keshdan qaytar
        if not products and cached:
            _, cached_products = cached
            if cached_products:
                return Response({
                    'success': True,
                    'count': len(cached_products),
                    'products': cached_products,
                })

        # Keshga saqlash
        if products:
            _MENU_CACHE[business_id] = (_time.time(), products)

        return Response({
            'success': True,
            'count': len(products),
            'products': products,
        })


class PrinterAgentSyncView(APIView):
    """POST /api/v2/printer/agent-sync/
    Agent printer qo'shganda backend bilan sync qiladi.
    Printer yaratadi yoki topadi, mahsulot ulashlarini yangilaydi.
    """
    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '').strip()

        try:
            cred = AgentCredential.objects.get(username=username, is_active=True)
        except AgentCredential.DoesNotExist:
            return Response({'success': False, 'error': 'Auth xato'}, status=401)
        if not cred.check_password(password):
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

class AgentCredentialListView(APIView):
    """GET /api/v2/agent-credential/list/ - Barcha agent loginlar"""

    def get(self, request):
        business_id = request.GET.get('business_id')
        qs = AgentCredential.objects.all().order_by('-created_at')
        if business_id:
            qs = qs.filter(business_id=business_id)
        data = []
        for c in qs:
            data.append({
                'id': c.id,
                'business_id': c.business_id,
                'business_name': c.business_name,
                'username': c.username,
                'password': c.password,
                'is_active': c.is_active,
                'note': c.note,
                'created_at': c.created_at.isoformat(),
            })
        return Response({'success': True, 'result': data})


class AgentCredentialCreateView(APIView):
    """POST /api/v2/agent-credential/create/ - Yangi agent login qo'shish"""

    def post(self, request):
        business_id = request.data.get('business_id')
        business_name = request.data.get('business_name', '')
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '').strip()
        note = request.data.get('note', '')
        is_active = request.data.get('is_active', True)

        if not business_id or not username or not password:
            return Response({
                'success': False,
                'error': 'business_id, username va password majburiy',
            }, status=status.HTTP_400_BAD_REQUEST)

        if AgentCredential.objects.filter(username=username).exists():
            return Response({
                'success': False,
                'error': f"'{username}' username allaqachon mavjud",
            }, status=status.HTTP_400_BAD_REQUEST)

        cred = AgentCredential.objects.create(
            business_id=business_id,
            business_name=business_name,
            username=username,
            password=password,
            note=note,
            is_active=is_active,
        )
        return Response({
            'success': True,
            'result': {
                'id': cred.id,
                'business_id': cred.business_id,
                'business_name': cred.business_name,
                'username': cred.username,
                'password': cred.password,
                'is_active': cred.is_active,
                'note': cred.note,
                'created_at': cred.created_at.isoformat(),
            },
        }, status=status.HTTP_201_CREATED)


class AgentCredentialUpdateView(APIView):
    """PUT /api/v2/agent-credential/{id}/update/"""

    def put(self, request, pk):
        try:
            cred = AgentCredential.objects.get(pk=pk)
        except AgentCredential.DoesNotExist:
            return Response({'success': False, 'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)

        for field in ('business_name', 'password', 'note', 'is_active'):
            if field in request.data:
                setattr(cred, field, request.data[field])

        new_username = request.data.get('username', '').strip()
        if new_username and new_username != cred.username:
            if AgentCredential.objects.filter(username=new_username).exists():
                return Response({
                    'success': False,
                    'error': f"'{new_username}' username allaqachon mavjud",
                }, status=status.HTTP_400_BAD_REQUEST)
            cred.username = new_username

        cred.save()
        return Response({
            'success': True,
            'result': {
                'id': cred.id,
                'business_id': cred.business_id,
                'business_name': cred.business_name,
                'username': cred.username,
                'password': cred.password,
                'is_active': cred.is_active,
                'note': cred.note,
                'created_at': cred.created_at.isoformat(),
            },
        })

    patch = put


class AgentCredentialDeleteView(APIView):
    """DELETE /api/v2/agent-credential/{id}/delete/"""

    def delete(self, request, pk):
        try:
            cred = AgentCredential.objects.get(pk=pk)
        except AgentCredential.DoesNotExist:
            return Response({'success': False, 'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)
        cred.delete()
        return Response({'success': True})


# ============================================================
# ORDER SERVICE CRUD (Tashqi servislar - Nonbor + boshqalar)
# ============================================================

def _order_service_dict(s):
    return {
        'id': s.id,
        'template_id': s.template_id,
        'template_name': s.template.name if s.template else None,
        'business_id': s.business_id,
        'business_name': s.business_name,
        'service_name': s.service_name,
        'api_url': s.api_url,
        'api_secret': s.api_secret[:4] + '****' if len(s.api_secret) > 4 else '****',
        'bot_token': s.bot_token[:8] + '****' if len(s.bot_token) > 8 else '****',
        'poll_enabled': s.poll_enabled,
        'poll_interval': s.poll_interval,
        'last_poll_at': s.last_poll_at.isoformat() if s.last_poll_at else None,
        'is_active': s.is_active,
        'created_at': s.created_at.isoformat(),
    }


class OrderServiceListView(APIView):
    """GET /api/v2/order-service/list/?business_id=<id>"""

    def get(self, request):
        business_id = request.GET.get('business_id')
        qs = OrderService.objects.all().order_by('business_id', 'service_name')
        if business_id:
            qs = qs.filter(business_id=business_id)
        return Response({'success': True, 'result': [_order_service_dict(s) for s in qs]})


class OrderServiceCreateView(APIView):
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

def _template_dict(t, request=None):
    logo_url = None
    if t.logo:
        logo_url = t.logo.url
        if request:
            logo_url = request.build_absolute_uri(t.logo.url)
    return {
        'id': t.id,
        'name': t.name,
        'slug': t.slug,
        'description': t.description,
        'icon': t.icon,
        'color': t.color,
        'logo': logo_url,
        'base_api_url': t.base_api_url,
        'default_poll_interval': t.default_poll_interval,
        'is_active': t.is_active,
        'sort_order': t.sort_order,
        'created_at': t.created_at.isoformat(),
        'connected_count': t.services.filter(is_active=True).count(),
    }


class IntegrationTemplateListView(APIView):
    """GET /api/v2/integration-template/list/"""

    def get(self, request):
        qs = IntegrationTemplate.objects.all()
        if request.GET.get('active_only') == 'true':
            qs = qs.filter(is_active=True)
        return Response({'success': True, 'result': [_template_dict(t, request) for t in qs]})


class IntegrationTemplateCreateView(APIView):
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
            t.logo = request.FILES['logo']
            t.save()
        return Response({'success': True, 'result': _template_dict(t, request)}, status=status.HTTP_201_CREATED)


class IntegrationTemplateUpdateView(APIView):
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

class ReceiptTemplateListView(APIView):
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
    """GET /api/v2/receipt-template/<business_id>/detail/"""

    def get(self, request, business_id):
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

class NotificationListView(APIView):
    """GET /api/v2/notification/list/?business_id=X&is_read=false"""

    def get(self, request):
        qs = PrinterNotification.objects.all()
        biz = request.query_params.get('business_id')
        if biz:
            qs = qs.filter(business_id=biz)
        is_read = request.query_params.get('is_read')
        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() == 'true')
        qs = qs[:50]
        return Response({
            'success': True,
            'result': PrinterNotificationSerializer(qs, many=True).data,
        })


class NotificationUnreadCountView(APIView):
    """GET /api/v2/notification/unread-count/?business_id=X"""

    def get(self, request):
        qs = PrinterNotification.objects.filter(is_read=False)
        biz = request.query_params.get('business_id')
        if biz:
            qs = qs.filter(business_id=biz)
        return Response({
            'success': True,
            'count': qs.count(),
        })


class NotificationMarkReadView(APIView):
    """POST /api/v2/notification/mark-read/
    Body: { ids: [1,2,3] }  yoki  { all: true, business_id: X }"""

    def post(self, request):
        ids = request.data.get('ids', [])
        mark_all = request.data.get('all', False)
        biz = request.data.get('business_id')

        if mark_all:
            qs = PrinterNotification.objects.filter(is_read=False)
            if biz:
                qs = qs.filter(business_id=biz)
            count = qs.update(is_read=True)
        elif ids:
            count = PrinterNotification.objects.filter(
                id__in=ids, is_read=False
            ).update(is_read=True)
        else:
            return Response({
                'success': False,
                'error': 'ids yoki all kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'marked': count})


class NotificationConfigSaveView(APIView):
    """POST /api/v2/notification-config/save/ — upsert"""

    def post(self, request):
        biz_id = request.data.get('business_id')
        if not biz_id:
            return Response({
                'success': False,
                'error': 'business_id kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        obj, created = NotificationConfig.objects.update_or_create(
            business_id=biz_id,
            defaults={
                'business_name': request.data.get('business_name', ''),
                'telegram_bot_token': request.data.get('telegram_bot_token', ''),
                'telegram_chat_id': request.data.get('telegram_chat_id', ''),
                'telegram_enabled': request.data.get('telegram_enabled', False),
                'cloud_timeout_minutes': request.data.get('cloud_timeout_minutes', 5),
            }
        )
        return Response({
            'success': True,
            'created': created,
            'result': NotificationConfigSerializer(obj).data,
        })


class NotificationConfigDetailView(APIView):
    """GET /api/v2/notification-config/{business_id}/detail/"""

    def get(self, request, business_id):
        try:
            obj = NotificationConfig.objects.get(business_id=business_id)
        except NotificationConfig.DoesNotExist:
            return Response({'success': True, 'result': None})
        return Response({
            'success': True,
            'result': NotificationConfigSerializer(obj).data,
        })


class NotificationTestTelegramView(APIView):
    """POST /api/v2/notification-config/test-telegram/"""

    def post(self, request):
        bot_token = request.data.get('telegram_bot_token', '')
        chat_id = request.data.get('telegram_chat_id', '')

        if not bot_token or not chat_id:
            return Response({
                'success': False,
                'error': 'bot_token va chat_id kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        from .services.notification_service import send_telegram_message
        text = "\u2705 Test xabar - Nonbor Printer bildirishnomalar ishlayapti!"
        sent = send_telegram_message(bot_token, chat_id, text)

        return Response({
            'success': sent,
            'message': 'Xabar yuborildi' if sent else "Xabar yuborib bo'lmadi",
        })


# ============================================================
# AGENT WEB DASHBOARD
# ============================================================

def agent_dashboard(request):
    """Web-based Print Agent dashboard — Android va kompyuterda ishlaydi"""
    return render(request, 'agent_dashboard.html')
