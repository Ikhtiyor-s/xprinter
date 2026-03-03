import logging

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Printer, PrinterCategory, PrinterProduct, PrintJob, NonborConfig, AgentCredential
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
)
from .services.print_service import (
    print_order,
    retry_print_job,
    send_test_print,
)
from .services.nonbor_api import NonborAPI, poll_and_print

logger = logging.getLogger(__name__)


# ============================================================
# PRINTER CRUD
# ============================================================

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
    Agent har 3 soniyada shu endpointga so'rov yuboradi."""
    pass  # no explicit permission, uses global AllowAny

    def get(self, request):
        business_id = request.query_params.get('business_id')
        if not business_id:
            return Response({
                'success': False,
                'error': 'business_id parametri kerak',
            }, status=status.HTTP_400_BAD_REQUEST)

        # Faqat pending joblar (cloud printerlar uchun)
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


class PrintWebhookView(APIView):
    """POST /api/v2/print-job/webhook/
    Nonbor backenddan webhook - buyurtma statusi o'zgarganda avtomatik chop etish"""
    permission_classes = []  # Webhook - autentifikatsiyasiz (secret bilan)

    def post(self, request):
        # Webhook secret tekshirish
        webhook_secret = request.headers.get('X-Webhook-Secret', '')
        # TODO: settings.py dan PRINTER_WEBHOOK_SECRET bilan solishtirish
        # if webhook_secret != settings.PRINTER_WEBHOOK_SECRET:
        #     return Response({'error': 'Invalid secret'}, status=403)

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


class AgentAuthView(APIView):
    """POST /api/v2/agent/auth/
    Print Agent uchun autentifikatsiya.
    Admin har bir biznesga alohida login/parol beradi.
    {username, password} → {business_id, business_name}"""

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


class NonborMenuView(APIView):
    """GET /api/v2/nonbor/menu/<business_id>/
    Agent uchun: biznes mahsulotlar ro'yxatini olish (Nonbor API proxy)
    Auth: ?username=...&password=...
    """
    def get(self, request, business_id):
        username = request.GET.get('username', '').strip()
        password = request.GET.get('password', '').strip()

        # Agent autentifikatsiya
        try:
            cred = AgentCredential.objects.get(username=username, is_active=True)
        except AgentCredential.DoesNotExist:
            return Response({'success': False, 'error': 'Login topilmadi'}, status=401)
        if not cred.check_password(password) or cred.business_id != business_id:
            return Response({'success': False, 'error': 'Auth xato'}, status=401)

        # Nonbor config
        try:
            config = NonborConfig.objects.get(business_id=business_id, is_active=True)
        except NonborConfig.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Nonbor API sozlamasi topilmadi. Admin sozlash kerak.',
            }, status=404)

        # Nonbor API dan mahsulotlar
        api = NonborAPI(config)
        all_products = []
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
            all_products.extend(result)
            if len(result) < 100:
                break
            page += 1

        products = []
        for p in all_products:
            mc = p.get('menu_category') or {}
            cat = p.get('category') or {}
            products.append({
                'id': p.get('id'),
                'name': p.get('name') or p.get('title', ''),
                'category_id': mc.get('id') or cat.get('id'),
                'category_name': mc.get('name') or cat.get('name') or 'Boshqa',
            })

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
            }
        )

        # Mahsulot ulashlarini yangilash
        PrinterProduct.objects.filter(printer=printer, business_id=business_id).delete()
        for pid in product_ids:
            pid_int = int(pid)
            pname = product_names.get(str(pid), '') or product_names.get(pid, '')
            PrinterProduct.objects.create(
                printer=printer,
                product_id=pid_int,
                product_name=pname,
                business_id=business_id,
            )

        return Response({
            'success': True,
            'printer_id': printer.id,
            'created': created,
            'products_assigned': len(product_ids),
        })
