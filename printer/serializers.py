from rest_framework import serializers
from .models import (
    Printer, PrinterCategory, PrinterProduct, PrintJob,
    NonborConfig, ReceiptTemplate, NotificationConfig, PrinterNotification,
)


# ============================================================
# SHARED HELPERS
# ============================================================

def _validate_printer_connection(data, instance=None):
    """Printer connection_type ga qarab ip_address/usb_path/p8 tekshirish.
    Create va Update serializerlar uchun umumiy validatsiya."""
    conn = data.get('connection_type', getattr(instance, 'connection_type', Printer.CONNECTION_NETWORK))
    ip = data.get('ip_address', getattr(instance, 'ip_address', None))
    usb = data.get('usb_path', getattr(instance, 'usb_path', None))
    p8_sn = data.get('p8_device_sn', getattr(instance, 'p8_device_sn', None))
    p8_key = data.get('p8_key', getattr(instance, 'p8_key', None))

    if conn in (Printer.CONNECTION_NETWORK, Printer.CONNECTION_WIFI) and not ip:
        raise serializers.ValidationError({
            'ip_address': "Tarmoq/WiFi printer uchun IP manzil kiritish shart."
        })
    elif conn == Printer.CONNECTION_USB and not usb:
        raise serializers.ValidationError({
            'usb_path': "USB printer uchun path kiritish shart."
        })
    elif conn == Printer.CONNECTION_P8:
        if not p8_sn:
            raise serializers.ValidationError({
                'p8_device_sn': "Trendit P8 uchun qurilma seriya raqami (SN) kiritish shart."
            })
        if not p8_key:
            raise serializers.ValidationError({
                'p8_key': "Trendit P8 uchun API kaliti kiritish shart."
            })
    return data


def _validate_printer_exists(value):
    """printer_id mavjudligini tekshirish — umumiy validator"""
    if not Printer.objects.filter(id=value).exists():
        raise serializers.ValidationError("Printer topilmadi.")
    return value


# Buyurtma uchun umumiy fieldlar (PrintOrderSerializer va WebhookSerializer)
_ORDER_OPTIONAL_FIELDS = {
    'order_number': serializers.CharField(max_length=50, required=False, default='', allow_blank=True),
    'business_name': serializers.CharField(max_length=200, required=False, default='', allow_blank=True),
    'customer_name': serializers.CharField(max_length=200, required=False, default='', allow_blank=True),
    'customer_phone': serializers.CharField(max_length=20, required=False, default='', allow_blank=True),
    'customer_address': serializers.CharField(required=False, default='', allow_blank=True),
    'delivery_method': serializers.CharField(max_length=20, required=False, default='', allow_blank=True),
    'payment_method': serializers.CharField(max_length=20, required=False, default='', allow_blank=True),
    'order_type': serializers.CharField(max_length=20, required=False, default='', allow_blank=True),
    'scheduled_time': serializers.CharField(required=False, default='', allow_blank=True),
    'comment': serializers.CharField(required=False, default='', allow_blank=True),
}


class _OrderFieldsMixin:
    """PrintOrderSerializer va WebhookSerializer uchun umumiy fieldlar"""
    pass


# Dinamik ravishda mixin ga fieldlarni qo'shish
for _name, _field in _ORDER_OPTIONAL_FIELDS.items():
    setattr(_OrderFieldsMixin, _name, _field)


# ============================================================
# PRINTER SERIALIZERS
# ============================================================

_PRINTER_BASE_FIELDS = [
    'name', 'connection_type', 'ip_address', 'port', 'usb_path',
    'p8_device_sn', 'p8_key', 'p8_api_url',
    'printer_model', 'paper_width', 'is_active', 'auto_print', 'is_admin',
]


class PrinterCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Printer
        fields = ['business_id'] + _PRINTER_BASE_FIELDS

    def validate(self, data):
        return _validate_printer_connection(data)


class PrinterUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Printer
        fields = _PRINTER_BASE_FIELDS

    def validate(self, data):
        return _validate_printer_connection(data, instance=self.instance)


class PrinterListSerializer(serializers.ModelSerializer):
    categories_count = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()
    connection_info = serializers.SerializerMethodField()

    class Meta:
        model = Printer
        fields = [
            'id', 'business_id', *_PRINTER_BASE_FIELDS,
            'categories_count', 'products_count', 'connection_info',
            'created_at', 'updated_at',
        ]

    def get_categories_count(self, obj):
        return obj.categories.count()

    def get_products_count(self, obj):
        return obj.products.count()

    def get_connection_info(self, obj):
        if obj.connection_type in (Printer.CONNECTION_NETWORK, Printer.CONNECTION_WIFI):
            return f"{obj.ip_address}:{obj.port}" if obj.ip_address else ''
        if obj.connection_type == Printer.CONNECTION_USB:
            return obj.usb_path or ''
        if obj.connection_type == Printer.CONNECTION_P8:
            return f"SN:{obj.p8_device_sn}" if obj.p8_device_sn else 'P8 (SN yo\'q)'
        return ''


class PrinterDetailSerializer(serializers.ModelSerializer):
    categories = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()

    class Meta:
        model = Printer
        fields = [
            'id', 'business_id', *_PRINTER_BASE_FIELDS,
            'categories', 'products',
            'created_at', 'updated_at',
        ]

    def get_categories(self, obj):
        return PrinterCategorySerializer(obj.categories.all(), many=True).data

    def get_products(self, obj):
        return PrinterProductSerializer(obj.products.all(), many=True).data


# ============================================================
# PRINTER CATEGORY SERIALIZERS
# ============================================================

class PrinterCategorySerializer(serializers.ModelSerializer):
    printer_name = serializers.CharField(source='printer.name', read_only=True)

    class Meta:
        model = PrinterCategory
        fields = ['id', 'printer', 'printer_name', 'category_id', 'category_name', 'business_id']


class PrinterCategoryAssignSerializer(serializers.Serializer):
    printer_id = serializers.IntegerField(validators=[_validate_printer_exists])
    category_id = serializers.IntegerField()
    category_name = serializers.CharField(max_length=200, required=False, default='')
    business_id = serializers.IntegerField()

    def validate(self, data):
        if PrinterCategory.objects.filter(printer_id=data['printer_id'], category_id=data['category_id']).exists():
            raise serializers.ValidationError("Bu kategoriya allaqachon shu printerga ulangan.")
        return data


class PrinterCategoryBulkAssignSerializer(serializers.Serializer):
    printer_id = serializers.IntegerField(validators=[_validate_printer_exists])
    business_id = serializers.IntegerField()
    categories = serializers.ListField(
        child=serializers.DictField(),
        help_text="[{category_id: int, category_name: str}]"
    )


# ============================================================
# PRINTER PRODUCT SERIALIZERS
# ============================================================

class PrinterProductSerializer(serializers.ModelSerializer):
    printer_name = serializers.CharField(source='printer.name', read_only=True)

    class Meta:
        model = PrinterProduct
        fields = ['id', 'printer', 'printer_name', 'product_id', 'product_name', 'business_id']


class PrinterProductAssignSerializer(serializers.Serializer):
    printer_id = serializers.IntegerField(validators=[_validate_printer_exists])
    product_id = serializers.IntegerField()
    product_name = serializers.CharField(max_length=300, required=False, default='')
    business_id = serializers.IntegerField()

    def validate(self, data):
        if PrinterProduct.objects.filter(business_id=data['business_id'], product_id=data['product_id']).exists():
            raise serializers.ValidationError(
                "Bu mahsulot allaqachon boshqa printerga ulangan. Avval eski ulashni o'chiring."
            )
        return data


class PrinterProductBulkAssignSerializer(serializers.Serializer):
    printer_id = serializers.IntegerField(validators=[_validate_printer_exists])
    business_id = serializers.IntegerField()
    products = serializers.ListField(
        child=serializers.DictField(),
        help_text="[{product_id: int, product_name: str}]"
    )


# ============================================================
# PRINT JOB SERIALIZERS
# ============================================================

class PrintJobSerializer(serializers.ModelSerializer):
    printer_name = serializers.CharField(source='printer.name', read_only=True)
    can_retry = serializers.BooleanField(read_only=True)

    class Meta:
        model = PrintJob
        fields = [
            'id', 'printer', 'printer_name',
            'order_id', 'business_id', 'status',
            'content', 'items_data',
            'retry_count', 'max_retries', 'can_retry',
            'error_message',
            'created_at', 'printed_at',
        ]


class PrintOrderSerializer(serializers.Serializer):
    """
    Buyurtmani chop etish uchun.
    Ikkita format qabul qilinadi:

    1. Flat format (to'g'ridan):
       { business_id, order_id, items: [...], customer_name, ... }

    2. Nested format (nonbor-admin webhook):
       { business_id, service_type, copies, trigger,
         order: { id, state, client_name, client_phone, items, ... } }
    """
    business_id  = serializers.IntegerField()
    # items top-level (flat format)
    items = serializers.ListField(
        child=serializers.DictField(), required=False, default=list,
        help_text="[{product_name|name, quantity, price, ...}]"
    )
    # Nested order object (webhook format)
    order = serializers.DictField(required=False, default=dict)

    # Meta
    service_type = serializers.CharField(required=False, default='nonbor', allow_blank=True)
    copies       = serializers.IntegerField(required=False, default=1)
    trigger      = serializers.CharField(required=False, default='', allow_blank=True)

    # Flat fields (ham flat, ham order ichidan olinadi)
    order_id        = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    order_number    = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    business_name   = serializers.CharField(max_length=200, required=False, default='', allow_blank=True)
    customer_name   = serializers.CharField(max_length=200, required=False, default='', allow_blank=True)
    customer_phone  = serializers.CharField(max_length=50,  required=False, default='', allow_blank=True)
    customer_address= serializers.CharField(required=False, default='', allow_blank=True)
    delivery_method = serializers.CharField(max_length=50,  required=False, default='', allow_blank=True)
    payment_method  = serializers.CharField(max_length=200, required=False, default='', allow_blank=True)
    order_type      = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    scheduled_time  = serializers.CharField(required=False, default='', allow_blank=True)
    comment         = serializers.CharField(required=False, default='', allow_blank=True)
    total_price     = serializers.FloatField(required=False, default=0)

    def to_internal_value(self, data):
        result = super().to_internal_value(data)

        # Nested order dan flat maydonlarga ko'chirish
        order = result.get('order') or {}
        if order:
            def _get(*keys):
                for k in keys:
                    v = order.get(k, '')
                    if v:
                        return str(v)
                return ''

            if not result.get('order_id'):
                result['order_id'] = str(order.get('id', ''))
            if not result.get('order_number'):
                result['order_number'] = str(order.get('order_number', '') or order.get('id', ''))
            if not result.get('customer_name'):
                result['customer_name'] = _get('client_name', 'customer_name', 'user')
            if not result.get('customer_phone'):
                result['customer_phone'] = _get('client_phone', 'customer_phone', 'phone')
            if not result.get('customer_address'):
                result['customer_address'] = _get('delivery_address', 'customer_address', 'address')
            if not result.get('delivery_method'):
                result['delivery_method'] = _get('delivery_type', 'delivery_method')
            if not result.get('payment_method'):
                result['payment_method'] = _get('payment_type', 'payment_method')
            if not result.get('comment'):
                result['comment'] = _get('pre_comment', 'comment')
            if not result.get('total_price'):
                result['total_price'] = order.get('total_price', 0) or 0

            # Items nested order dan
            if not result.get('items'):
                raw_items = order.get('items') or order.get('order_items') or []
                items = []
                for it in raw_items:
                    items.append({
                        'name':       it.get('product_name') or it.get('name', ''),
                        'quantity':   it.get('quantity', 1),
                        'price':      it.get('price', 0),
                        'product_id': it.get('product_id') or it.get('id'),
                    })
                result['items'] = items

        return result


class WebhookSerializer(serializers.Serializer):
    """Nonbor/POS webhook - buyurtma statusi o'zgarganda"""
    order_id = serializers.CharField(max_length=100)   # UUID yoki int
    business_id = serializers.IntegerField()
    state = serializers.CharField(required=False, default='ACCEPTED', allow_blank=True)
    items = serializers.ListField(child=serializers.DictField(), required=False, default=list)

    # Umumiy order fieldlari
    order_number = serializers.CharField(required=False, default='', allow_blank=True)
    business_name = serializers.CharField(max_length=200, required=False, default='', allow_blank=True)
    customer_name = serializers.CharField(max_length=200, required=False, default='', allow_blank=True)
    customer_phone = serializers.CharField(max_length=20, required=False, default='', allow_blank=True)
    customer_address = serializers.CharField(required=False, default='', allow_blank=True)
    delivery_method = serializers.CharField(max_length=20, required=False, default='', allow_blank=True)
    payment_method = serializers.CharField(required=False, default='', allow_blank=True)
    order_type = serializers.CharField(max_length=20, required=False, default='', allow_blank=True)
    scheduled_time = serializers.CharField(required=False, default='', allow_blank=True)
    comment = serializers.CharField(required=False, default='', allow_blank=True)


# ============================================================
# NONBOR CONFIG SERIALIZERS
# ============================================================

_NONBOR_CONFIG_FIELDS = [
    'id', 'business_id', 'business_name',
    'api_url', 'api_secret', 'seller_id',
    'poll_enabled', 'poll_interval',
    'last_poll_at', 'is_active', 'created_at',
]


class NonborConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = NonborConfig
        fields = _NONBOR_CONFIG_FIELDS
        read_only_fields = ['id', 'last_poll_at', 'created_at']


class NonborConfigCreateSerializer(serializers.ModelSerializer):
    api_secret = serializers.CharField(required=False, allow_blank=True, default='')

    class Meta:
        model = NonborConfig
        fields = [f for f in _NONBOR_CONFIG_FIELDS if f not in ('id', 'last_poll_at', 'created_at')]

    def validate_business_id(self, value):
        if NonborConfig.objects.filter(business_id=value).exists():
            raise serializers.ValidationError("Bu biznes uchun allaqachon sozlama mavjud.")
        return value


class NonborConfigUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NonborConfig
        fields = ['business_name', 'api_url', 'api_secret', 'seller_id', 'poll_enabled', 'poll_interval', 'is_active']


# ============================================================
# RECEIPT TEMPLATE SERIALIZERS
# ============================================================

class ReceiptTemplateSerializer(serializers.ModelSerializer):
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)

    class Meta:
        model = ReceiptTemplate
        fields = [
            'id', 'business_id', 'business_name', 'template_type', 'template_type_display',
            'header_text', 'show_customer_info', 'show_other_printers',
            'show_comment', 'show_product_names',
            'footer_text', 'font_size', 'default_paper_width',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================
# NOTIFICATION SERIALIZERS
# ============================================================

class NotificationConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationConfig
        fields = [
            'id', 'business_id', 'business_name',
            'telegram_bot_token', 'telegram_chat_id', 'telegram_enabled',
            'cloud_timeout_minutes', 'is_active', 'created_at',
        ]


class PrinterNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrinterNotification
        fields = [
            'id', 'business_id', 'business_name', 'printer_name',
            'order_id', 'print_job_id', 'level',
            'title', 'message', 'is_read', 'telegram_sent',
            'created_at',
        ]
