from rest_framework import serializers
from .models import (
    Printer, PrinterCategory, PrinterProduct, PrintJob,
    NonborConfig, ReceiptTemplate, NotificationConfig, PrinterNotification,
)


# ============================================================
# PRINTER SERIALIZERS
# ============================================================

class PrinterCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Printer
        fields = [
            'business_id', 'name', 'connection_type',
            'ip_address', 'port', 'usb_path',
            'printer_model', 'paper_width',
            'is_active', 'auto_print', 'is_admin',
        ]

    def validate(self, data):
        conn = data.get('connection_type', Printer.CONNECTION_NETWORK)
        if conn in (Printer.CONNECTION_NETWORK, Printer.CONNECTION_WIFI):
            if not data.get('ip_address'):
                raise serializers.ValidationError({
                    'ip_address': "Tarmoq/WiFi printer uchun IP manzil kiritish shart."
                })
        elif conn == Printer.CONNECTION_USB:
            if not data.get('usb_path'):
                raise serializers.ValidationError({
                    'usb_path': "USB printer uchun path kiritish shart."
                })
        return data


class PrinterUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Printer
        fields = [
            'name', 'connection_type',
            'ip_address', 'port', 'usb_path',
            'printer_model', 'paper_width',
            'is_active', 'auto_print', 'is_admin',
        ]

    def validate(self, data):
        instance = self.instance
        conn = data.get('connection_type', instance.connection_type if instance else Printer.CONNECTION_NETWORK)
        ip = data.get('ip_address', instance.ip_address if instance else None)
        usb = data.get('usb_path', instance.usb_path if instance else None)

        if conn in (Printer.CONNECTION_NETWORK, Printer.CONNECTION_WIFI) and not ip:
            raise serializers.ValidationError({
                'ip_address': "Tarmoq/WiFi printer uchun IP manzil kiritish shart."
            })
        elif conn == Printer.CONNECTION_USB and not usb:
            raise serializers.ValidationError({
                'usb_path': "USB printer uchun path kiritish shart."
            })
        return data


class PrinterListSerializer(serializers.ModelSerializer):
    categories_count = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()
    connection_info = serializers.SerializerMethodField()

    class Meta:
        model = Printer
        fields = [
            'id', 'business_id', 'name', 'connection_type',
            'ip_address', 'port', 'usb_path',
            'printer_model', 'paper_width',
            'is_active', 'auto_print', 'is_admin',
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
        return ''


class PrinterDetailSerializer(serializers.ModelSerializer):
    categories = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()

    class Meta:
        model = Printer
        fields = [
            'id', 'business_id', 'name', 'connection_type',
            'ip_address', 'port', 'usb_path',
            'printer_model', 'paper_width',
            'is_active', 'auto_print', 'is_admin',
            'categories', 'products',
            'created_at', 'updated_at',
        ]

    def get_categories(self, obj):
        return PrinterCategorySerializer(
            obj.categories.all(), many=True
        ).data

    def get_products(self, obj):
        return PrinterProductSerializer(
            obj.products.all(), many=True
        ).data


# ============================================================
# PRINTER CATEGORY SERIALIZERS
# ============================================================

class PrinterCategorySerializer(serializers.ModelSerializer):
    printer_name = serializers.CharField(source='printer.name', read_only=True)

    class Meta:
        model = PrinterCategory
        fields = [
            'id', 'printer', 'printer_name',
            'category_id', 'category_name', 'business_id',
        ]


class PrinterCategoryAssignSerializer(serializers.Serializer):
    """Bitta kategoriyani printerga ulash"""
    printer_id = serializers.IntegerField()
    category_id = serializers.IntegerField()
    category_name = serializers.CharField(max_length=200, required=False, default='')
    business_id = serializers.IntegerField()

    def validate_printer_id(self, value):
        if not Printer.objects.filter(id=value).exists():
            raise serializers.ValidationError("Printer topilmadi.")
        return value

    def validate(self, data):
        exists = PrinterCategory.objects.filter(
            printer_id=data['printer_id'],
            category_id=data['category_id'],
        ).exists()
        if exists:
            raise serializers.ValidationError(
                "Bu kategoriya allaqachon shu printerga ulangan."
            )
        return data


class PrinterCategoryBulkAssignSerializer(serializers.Serializer):
    """Ko'plab kategoriyalarni printerga ulash"""
    printer_id = serializers.IntegerField()
    business_id = serializers.IntegerField()
    categories = serializers.ListField(
        child=serializers.DictField(),
        help_text="[{category_id: int, category_name: str}]"
    )

    def validate_printer_id(self, value):
        if not Printer.objects.filter(id=value).exists():
            raise serializers.ValidationError("Printer topilmadi.")
        return value


# ============================================================
# PRINTER PRODUCT SERIALIZERS
# ============================================================

class PrinterProductSerializer(serializers.ModelSerializer):
    printer_name = serializers.CharField(source='printer.name', read_only=True)

    class Meta:
        model = PrinterProduct
        fields = [
            'id', 'printer', 'printer_name',
            'product_id', 'product_name', 'business_id',
        ]


class PrinterProductAssignSerializer(serializers.Serializer):
    """Bitta mahsulotni printerga ulash"""
    printer_id = serializers.IntegerField()
    product_id = serializers.IntegerField()
    product_name = serializers.CharField(max_length=300, required=False, default='')
    business_id = serializers.IntegerField()

    def validate_printer_id(self, value):
        if not Printer.objects.filter(id=value).exists():
            raise serializers.ValidationError("Printer topilmadi.")
        return value

    def validate(self, data):
        exists = PrinterProduct.objects.filter(
            business_id=data['business_id'],
            product_id=data['product_id'],
        ).exists()
        if exists:
            raise serializers.ValidationError(
                "Bu mahsulot allaqachon boshqa printerga ulangan. "
                "Avval eski ulashni o'chiring."
            )
        return data


class PrinterProductBulkAssignSerializer(serializers.Serializer):
    """Ko'plab mahsulotlarni printerga ulash"""
    printer_id = serializers.IntegerField()
    business_id = serializers.IntegerField()
    products = serializers.ListField(
        child=serializers.DictField(),
        help_text="[{product_id: int, product_name: str}]"
    )

    def validate_printer_id(self, value):
        if not Printer.objects.filter(id=value).exists():
            raise serializers.ValidationError("Printer topilmadi.")
        return value


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
    """Buyurtmani chop etish uchun"""
    business_id = serializers.IntegerField()
    order_id = serializers.IntegerField()
    order_number = serializers.CharField(max_length=50, required=False, default='', allow_blank=True)
    business_name = serializers.CharField(max_length=200, required=False, default='', allow_blank=True)
    customer_name = serializers.CharField(max_length=200, required=False, default='', allow_blank=True)
    customer_phone = serializers.CharField(max_length=20, required=False, default='', allow_blank=True)
    customer_address = serializers.CharField(required=False, default='', allow_blank=True)
    delivery_method = serializers.CharField(max_length=20, required=False, default='', allow_blank=True)
    payment_method = serializers.CharField(max_length=20, required=False, default='', allow_blank=True)
    order_type = serializers.CharField(max_length=20, required=False, default='', allow_blank=True)
    scheduled_time = serializers.CharField(required=False, default='', allow_blank=True)
    comment = serializers.CharField(required=False, default='', allow_blank=True)
    items = serializers.ListField(
        child=serializers.DictField(),
        help_text="[{name, quantity, price, product_id, category_id, category_name}]"
    )


class WebhookSerializer(serializers.Serializer):
    """Nonbor webhook - buyurtma statusi o'zgarganda"""
    order_id = serializers.IntegerField()
    business_id = serializers.IntegerField()
    state = serializers.CharField()
    order_number = serializers.CharField(required=False, default='', allow_blank=True)
    business_name = serializers.CharField(required=False, default='', allow_blank=True)
    customer_name = serializers.CharField(required=False, default='', allow_blank=True)
    customer_phone = serializers.CharField(required=False, default='', allow_blank=True)
    customer_address = serializers.CharField(required=False, default='', allow_blank=True)
    delivery_method = serializers.CharField(required=False, default='', allow_blank=True)
    payment_method = serializers.CharField(required=False, default='', allow_blank=True)
    order_type = serializers.CharField(required=False, default='', allow_blank=True)
    scheduled_time = serializers.CharField(required=False, default='', allow_blank=True)
    comment = serializers.CharField(required=False, default='', allow_blank=True)
    items = serializers.ListField(
        child=serializers.DictField(),
        required=False, default=list,
    )


# ============================================================
# NONBOR CONFIG SERIALIZERS
# ============================================================

class NonborConfigSerializer(serializers.ModelSerializer):
    api_secret = serializers.SerializerMethodField()

    class Meta:
        model = NonborConfig
        fields = [
            'id', 'business_id', 'business_name',
            'api_url', 'api_secret_masked', 'seller_id',
            'poll_enabled', 'poll_interval',
            'last_poll_at', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'last_poll_at', 'created_at']

    def get_api_secret(self, obj):
        if obj.api_secret:
            return obj.api_secret[:4] + '***' + obj.api_secret[-2:]
        return ""


class NonborConfigCreateSerializer(serializers.ModelSerializer):
    api_secret = serializers.CharField(required=False, allow_blank=True, default='')

    class Meta:
        model = NonborConfig
        fields = [
            'business_id', 'business_name',
            'api_url', 'api_secret', 'seller_id',
            'poll_enabled', 'poll_interval', 'is_active',
        ]

    def validate_business_id(self, value):
        if NonborConfig.objects.filter(business_id=value).exists():
            raise serializers.ValidationError(
                "Bu biznes uchun allaqachon sozlama mavjud."
            )
        return value


class NonborConfigUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NonborConfig
        fields = [
            'business_name', 'api_url', 'api_secret',
            'seller_id', 'poll_enabled', 'poll_interval', 'is_active',
        ]


# ============================================================
# RECEIPT TEMPLATE SERIALIZERS
# ============================================================

class ReceiptTemplateSerializer(serializers.ModelSerializer):
    template_type_display = serializers.CharField(
        source='get_template_type_display', read_only=True
    )

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
    telegram_bot_token = serializers.SerializerMethodField()

    class Meta:
        model = NotificationConfig
        fields = [
            'id', 'business_id', 'business_name',
            'telegram_bot_token', 'telegram_chat_id', 'telegram_enabled',
            'cloud_timeout_minutes', 'is_active', 'created_at',
        ]

    def get_telegram_bot_token(self, obj):
        if obj.telegram_bot_token:
            return obj.telegram_bot_token[:8] + '***'
        return ""

class PrinterNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrinterNotification
        fields = [
            'id', 'business_id', 'business_name', 'printer_name',
            'order_id', 'print_job_id', 'level',
            'title', 'message', 'is_read', 'telegram_sent',
            'created_at',
        ]
