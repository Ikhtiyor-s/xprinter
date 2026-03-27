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


class AgentAuthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
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
                'error': 'Login yoki parol xato',
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
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = [IsAgentAuthenticated]
    """GET /api/v2/nonbor/menu/<business_id>/
    Agent uchun: biznes mahsulotlar ro'yxatini olish (Nonbor API proxy)
    Auth: ?username=...&password=...
    """
    def get(self, request, business_id):
        # Auth is now handled by AgentTokenAuthentication header
        force_refresh = request.GET.get('refresh', '').strip() == '1'

        # Agent credential from authentication
        cred = getattr(request.user, 'credential', None)
        if not cred or cred.business_id != business_id:
            return Response({'success': False, 'error': "Bu biznesga ruxsat yo'q"}, status=403)

        # Keshdan qaytarish (agar yangi so'rov emas bo'lsa)
        from django.core.cache import cache as _cache
        cached = _cache.get(f"menu_{business_id}")
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
                    business_name=getattr(cred, 'business_name', '') or f'Biznes #{business_id}',
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
            _cache.set(f"menu_{business_id}", (_time.time(), products), _MENU_CACHE_TTL)

        return Response({
            'success': True,
            'count': len(products),
            'products': products,
        })



class AgentCredentialListView(APIView):
    permission_classes = [IsAuthenticated]
    """GET /api/v2/agent-credential/list/ - Barcha agent loginlar"""

    def get(self, request):
        biz_id, err = enforce_business_id(request)
        if err:
            return err
        qs = AgentCredential.objects.all().order_by('-created_at')
        if biz_id:
            qs = qs.filter(business_id=biz_id)
        data = []
        for c in qs:
            data.append({
                'id': c.id,
                'business_id': c.business_id,
                'business_name': c.business_name,
                'username': c.username,
                'password': '********' if c.password else '',
                'is_active': c.is_active,
                'note': c.note,
                'created_at': c.created_at.isoformat(),
            })
        return Response({'success': True, 'result': data})



class AgentCredentialCreateView(APIView):
    permission_classes = [IsAuthenticated]
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
    permission_classes = [IsAuthenticated]
    """PUT /api/v2/agent-credential/{id}/update/"""

    def put(self, request, pk):
        try:
            cred = AgentCredential.objects.get(pk=pk)
        except AgentCredential.DoesNotExist:
            return Response({'success': False, 'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)

        for field in ('business_name', 'note', 'is_active'):
            if field in request.data:
                setattr(cred, field, request.data[field])

        # Parol faqat yangi qiymat yuborilganda o'zgaradi
        new_password = request.data.get('password', '')
        if new_password and new_password != '********':
            cred.set_password(new_password)

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
                'password': '********',
                'is_active': cred.is_active,
                'note': cred.note,
                'created_at': cred.created_at.isoformat(),
            },
        })

    patch = put



class AgentCredentialDeleteView(APIView):
    permission_classes = [IsAuthenticated]
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

