from django.db import models
from django.contrib.auth.hashers import make_password, check_password as django_check_password
from django.utils import timezone


class Printer(models.Model):
    """Oshxona printeri - har bir biznesda bir nechta printer bo'lishi mumkin"""

    CONNECTION_NETWORK = 'network'
    CONNECTION_USB = 'usb'
    CONNECTION_CLOUD = 'cloud'
    CONNECTION_WIFI = 'wifi'
    CONNECTION_P8 = 'p8'
    CONNECTION_CHOICES = [
        (CONNECTION_NETWORK, 'Tarmoq (IP) - lokal'),
        (CONNECTION_USB, 'USB - lokal'),
        (CONNECTION_CLOUD, 'Cloud - masofadan (agent orqali)'),
        (CONNECTION_WIFI, 'WiFi - simsiz tarmoq'),
        (CONNECTION_P8, 'Trendit P8 - Smart Cloud Printer'),
    ]

    PAPER_58 = 58
    PAPER_80 = 80
    PAPER_CHOICES = [
        (PAPER_58, '58mm'),
        (PAPER_80, '80mm'),
    ]

    business_id = models.IntegerField(
        db_index=True,
        help_text="Nonbor business ID"
    )
    name = models.CharField(
        max_length=100,
        help_text="Printer nomi, masalan: Salat printer, Osh printer"
    )
    connection_type = models.CharField(
        max_length=10,
        choices=CONNECTION_CHOICES,
        default=CONNECTION_NETWORK,
    )
    ip_address = models.GenericIPAddressField(
        null=True, blank=True,
        help_text="Tarmoq printerlari uchun IP manzil"
    )
    port = models.IntegerField(
        default=9100,
        help_text="TCP port (standart: 9100)"
    )
    usb_path = models.CharField(
        max_length=200,
        null=True, blank=True,
        help_text="USB printerlari uchun path, masalan: /dev/usb/lp0"
    )
    printer_model = models.CharField(
        max_length=100,
        null=True, blank=True,
        help_text="Printer modeli, masalan: Xprinter XP-80C"
    )
    paper_width = models.IntegerField(
        choices=PAPER_CHOICES,
        default=PAPER_80,
        help_text="Qog'oz kengligi: 58mm yoki 80mm"
    )
    # P8 Cloud Printer sozlamalari
    p8_device_sn = models.CharField(
        max_length=100,
        null=True, blank=True,
        help_text="Trendit P8 qurilma seriya raqami (SN)"
    )
    p8_key = models.CharField(
        max_length=200,
        null=True, blank=True,
        help_text="Trendit P8 API kaliti (access key)"
    )
    p8_api_url = models.CharField(
        max_length=500,
        null=True, blank=True,
        default='https://api.trenditen.com',
        help_text="Trendit P8 bulut API manzili"
    )

    is_active = models.BooleanField(default=True)
    auto_print = models.BooleanField(
        default=True,
        help_text="Buyurtma ACCEPTED bo'lganda avtomatik chop etish"
    )
    is_admin = models.BooleanField(
        default=False,
        help_text="Admin printer - barcha buyurtmalar umumiy ko'rsatiladi"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'printer'
        ordering = ['business_id', 'name']

    def __str__(self):
        if self.connection_type in (self.CONNECTION_NETWORK, self.CONNECTION_WIFI):
            conn = self.ip_address
        else:
            conn = self.usb_path
        return f"{self.name} ({conn})"


class NonborConfig(models.Model):
    """Nonbor API ulanish sozlamalari - har bir biznes uchun"""

    business_id = models.IntegerField(
        unique=True,
        help_text="Nonbor business ID"
    )
    business_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Biznes nomi (avtomatik olinadi)"
    )
    api_url = models.CharField(
        max_length=500,
        default='https://prod.nonbor.uz/api/v2',
        help_text="Nonbor API URL"
    )
    api_secret = models.CharField(
        max_length=200,
        default='',
        blank=True,
        help_text="X-Telegram-Bot-Secret header qiymati"
    )
    seller_id = models.IntegerField(
        null=True, blank=True,
        help_text="Nonbor seller ID (buyurtmalarni olish uchun)"
    )
    poll_enabled = models.BooleanField(
        default=False,
        help_text="Avtomatik polling yoqilganmi"
    )
    poll_interval = models.IntegerField(
        default=5,
        help_text="Polling intervali (sekundlarda)"
    )
    last_poll_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Oxirgi polling vaqti"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'nonbor_config'

    def __str__(self):
        return f"Nonbor #{self.business_id} - {self.business_name}"


class PrinterCategory(models.Model):
    """Printer va kategoriya o'rtasidagi bog'lanish.
    Har bir kategoriya faqat bitta printerga ulangan bo'lishi kerak."""

    printer = models.ForeignKey(
        Printer,
        on_delete=models.CASCADE,
        related_name='categories',
    )
    category_id = models.IntegerField(
        help_text="Nonbor MenuCategory ID"
    )
    category_name = models.CharField(
        max_length=200,
        blank=True, default='',
        help_text="Kategoriya nomi (kesh)"
    )
    business_id = models.IntegerField(db_index=True)

    class Meta:
        db_table = 'printer_category'
        unique_together = ('printer', 'category_id')

    def __str__(self):
        return f"{self.category_name} → {self.printer.name}"


class PrinterProduct(models.Model):
    """Alohida mahsulotni printerga ulash.
    Mahsulot ulashi kategoriya ulashidan USTUN turadi.
    Masalan: 'Olivye salat' → Printer 1 (garchi kategoriyasi boshqa printerga ulangan bo'lsa ham)"""

    printer = models.ForeignKey(
        Printer,
        on_delete=models.CASCADE,
        related_name='products',
    )
    product_id = models.IntegerField(
        help_text="Nonbor Product ID"
    )
    product_name = models.CharField(
        max_length=300,
        blank=True, default='',
        help_text="Mahsulot nomi (kesh)"
    )
    business_id = models.IntegerField(db_index=True)

    class Meta:
        db_table = 'printer_product'
        unique_together = ('business_id', 'product_id')

    def __str__(self):
        return f"{self.product_name} → {self.printer.name}"


class AgentCredential(models.Model):
    """Print Agent uchun login/parol - admin tomonidan har bir biznesga beriladi"""

    business_id = models.IntegerField(
        help_text="Nonbor business ID"
    )
    business_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Biznes nomi (agent ekranida ko'rsatiladi)"
    )
    username = models.CharField(
        max_length=100, unique=True,
        help_text="Agent login (sotuvchiga beriladi)"
    )
    password = models.CharField(
        max_length=200,
        help_text="Agent parol (hashed)"
    )
    is_active = models.BooleanField(default=True)
    note = models.CharField(
        max_length=300, blank=True, default='',
        help_text="Izoh, masalan: 'Samarqand filiali'"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'agent_credential'
        verbose_name = 'Agent login'
        verbose_name_plural = 'Agent loginlar'

    def __str__(self):
        return f"{self.username} → Biznes #{self.business_id} ({self.business_name})"

    def set_password(self, raw_password: str):
        self.password = make_password(raw_password)

    def check_password(self, raw: str) -> bool:
        return django_check_password(raw, self.password)

    def save(self, *args, **kwargs):
        # Yangi parol yoki plaintext parol bo'lsa — hash qilish
        if self.password and not self.password.startswith(('pbkdf2_sha256$', 'argon2$', 'bcrypt$')):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)


class NotificationConfig(models.Model):
    """Printer xatolik bildirishnomalari sozlamalari - har bir biznes uchun"""

    business_id = models.IntegerField(
        unique=True, db_index=True,
        help_text="Nonbor business ID"
    )
    business_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Biznes nomi (kesh)"
    )
    telegram_bot_token = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Telegram bot token"
    )
    telegram_chat_id = models.CharField(
        max_length=100, blank=True, default='',
        help_text="Telegram chat/group ID"
    )
    telegram_enabled = models.BooleanField(
        default=False,
        help_text="Telegram xabar yuborish yoqilganmi"
    )
    cloud_timeout_seconds = models.IntegerField(
        default=20,
        help_text="Cloud printer javob berish vaqti (sekund). Default: 20"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notification_config'

    def __str__(self):
        return f"Bildirishnoma #{self.business_id} - {self.business_name}"


class PrinterNotification(models.Model):
    """Printer xatolik bildirishnomalari - admin panelda ko'rsatish uchun"""

    LEVEL_ERROR = 'error'
    LEVEL_WARNING = 'warning'
    LEVEL_INFO = 'info'
    LEVEL_CHOICES = [
        (LEVEL_ERROR, 'Xatolik'),
        (LEVEL_WARNING, 'Ogohlantirish'),
        (LEVEL_INFO, "Ma'lumot"),
    ]

    business_id = models.IntegerField(db_index=True)
    business_name = models.CharField(max_length=200, blank=True, default='')
    printer_name = models.CharField(max_length=100, blank=True, default='')
    order_id = models.IntegerField(null=True, blank=True)
    print_job_id = models.IntegerField(null=True, blank=True)
    level = models.CharField(
        max_length=10, choices=LEVEL_CHOICES, default=LEVEL_ERROR,
    )
    title = models.CharField(max_length=300)
    message = models.TextField(blank=True, default='')
    is_read = models.BooleanField(default=False, db_index=True)
    telegram_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'printer_notification'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.level}] {self.title}"


class IntegrationTemplate(models.Model):
    """Tayyor integratsiya shablonlari - admin tomonidan yaratiladi.
    Har bir shablon bitta integratsiya turini ifodalaydi (Nonbor, iiko, R-Keeper va h.k.)"""

    name = models.CharField(max_length=200, help_text="Shablon nomi: Nonbor, iiko, R-Keeper")
    slug = models.SlugField(unique=True, help_text="URL-friendly nom: nonbor, iiko, r-keeper")
    description = models.TextField(blank=True, default='', help_text="Qisqa tavsif")
    icon = models.CharField(max_length=50, default='🔗', help_text="Emoji yoki icon nomi")
    color = models.CharField(max_length=20, default='#1890ff', help_text="Kartochka rangi (hex)")
    logo = models.ImageField(upload_to='integration_logos/', blank=True, null=True, help_text="Integratsiya logotipi")
    base_api_url = models.CharField(max_length=500, blank=True, default='', help_text="Default API URL")
    default_poll_interval = models.IntegerField(default=10, help_text="Default polling intervali (s)")
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0, help_text="Tartiblash uchun")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'integration_template'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f"{self.icon} {self.name}"


class OrderService(models.Model):
    """Tashqi buyurtma servislari - Nonbor emas, boshqa tizimlar ham ulanishi mumkin.
    Masalan: Yandex Food, Express24, iiko va h.k.
    Har bir servis uchun API URL va autentifikatsiya ma'lumotlari saqlanadi."""

    template = models.ForeignKey(
        IntegrationTemplate, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='services',
        help_text="Qaysi shablon asosida yaratilgan"
    )
    business_id = models.IntegerField(
        db_index=True,
        help_text="Nonbor business ID"
    )
    business_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Biznes nomi (kesh)"
    )
    service_name = models.CharField(
        max_length=200,
        help_text="Servis nomi, masalan: Yandex Food, Express24"
    )
    api_url = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Buyurtmalarni olish uchun API URL (ixtiyoriy)"
    )
    api_secret = models.CharField(
        max_length=300, blank=True, default='',
        help_text="API token yoki maxfiy kalit (ixtiyoriy)"
    )
    bot_token = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Telegram bot token (ixtiyoriy)"
    )
    poll_enabled = models.BooleanField(
        default=False,
        help_text="Avtomatik polling yoqilganmi"
    )
    poll_interval = models.IntegerField(
        default=10,
        help_text="Polling intervali (sekundlarda)"
    )
    last_poll_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Oxirgi polling vaqti"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_service'
        ordering = ['business_id', 'service_name']

    def __str__(self):
        return f"{self.service_name} → Biznes #{self.business_id}"


class PrintJob(models.Model):
    """Chop etish tarixi va navbat"""

    STATUS_PENDING = 'pending'
    STATUS_PRINTING = 'printing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Kutilmoqda'),
        (STATUS_PRINTING, 'Chop etilmoqda'),
        (STATUS_COMPLETED, 'Tayyor'),
        (STATUS_FAILED, 'Xatolik'),
    ]

    printer = models.ForeignKey(
        Printer,
        on_delete=models.CASCADE,
        related_name='print_jobs',
    )
    order_id = models.IntegerField(
        db_index=True,
        help_text="Buyurtma ID (platformadan)"
    )
    business_id = models.IntegerField(db_index=True)
    service_type = models.CharField(
        max_length=50, default='nonbor', db_index=True,
        help_text="Buyurtma manbasi: nonbor, telegram, yandex, uzum, express24, iiko, custom"
    )
    external_order_id = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Tashqi tizim buyurtma ID (dublikat oldini olish uchun)"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    content = models.TextField(
        blank=True, default='',
        help_text="Chop etish uchun matn"
    )
    items_data = models.JSONField(
        default=list,
        help_text="Taomlar ma'lumoti [{name, quantity, price, category_id}]"
    )
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    printed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'print_job'
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.order_id} → {self.printer.name} [{self.status}]"

    def mark_completed(self):
        self.status = self.STATUS_COMPLETED
        self.printed_at = timezone.now()
        self.save(update_fields=['status', 'printed_at'])

    def mark_failed(self, error: str):
        self.status = self.STATUS_FAILED
        self.error_message = error
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count'])

    @property
    def can_retry(self):
        return self.retry_count < self.max_retries


class ReceiptTemplate(models.Model):
    """Chek shabloni — har bir biznes + buyurtma turi uchun bitta.
    Masalan: Yetkazish cheki, Olib ketish cheki, Zalda cheki."""

    TYPE_DELIVERY = 'delivery'
    TYPE_PICKUP = 'pickup'
    TYPE_DINE_IN = 'dine_in'
    TYPE_SCHED_DEL = 'sched_del'
    TYPE_SCHED_PICK = 'sched_pick'
    TYPE_ADMIN = 'admin'
    TYPE_CHOICES = [
        (TYPE_DELIVERY, 'Yetkazib berish'),
        (TYPE_PICKUP, 'Olib ketish'),
        (TYPE_DINE_IN, 'Zalda'),
        (TYPE_SCHED_DEL, 'Reja yetkazish'),
        (TYPE_SCHED_PICK, 'Reja olib ketish'),
        (TYPE_ADMIN, 'Admin printer'),
    ]

    FONT_NORMAL = 'normal'
    FONT_LARGE = 'large'
    FONT_CHOICES = [
        (FONT_NORMAL, 'Normal'),
        (FONT_LARGE, 'Katta'),
    ]

    business_id = models.IntegerField(
        db_index=True,
        help_text="Nonbor business ID"
    )
    business_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Biznes nomi (kesh)"
    )
    template_type = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default=TYPE_DELIVERY,
        help_text="Buyurtma turi: delivery, pickup, dine_in"
    )

    # Header
    header_text = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Sarlavha matni (bo'sh bo'lsa business_name ishlatiladi)"
    )

    # Ko'rsatish / yashirish
    show_customer_info = models.BooleanField(
        default=True,
        help_text="Mijoz ma'lumotlari (ism, telefon, manzil)"
    )
    show_other_printers = models.BooleanField(
        default=True,
        help_text="Boshqa printerlar bo'limi"
    )
    show_comment = models.BooleanField(
        default=True,
        help_text="Mijoz izohi"
    )
    show_product_names = models.BooleanField(
        default=True,
        help_text="Mahsulot nomlari katta shriftda (oddiy printerlar uchun)"
    )

    # Footer
    footer_text = models.CharField(
        max_length=300, blank=True, default='Rahmat!',
        help_text="Chek pastida chiqadigan matn"
    )

    # Shrift va qog'oz
    font_size = models.CharField(
        max_length=10, choices=FONT_CHOICES, default=FONT_NORMAL,
    )
    default_paper_width = models.IntegerField(
        choices=[(58, '58mm'), (80, '80mm')],
        default=80,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'receipt_template'
        unique_together = ('business_id', 'template_type')

    def __str__(self):
        return f"Chek shablon → Biznes #{self.business_id} ({self.get_template_type_display()})"


class SellerProfile(models.Model):
    """Seller profili — Django User va business_id bog'lash.
    Har bir seller faqat o'z biznesining ma'lumotlarini ko'radi.
    is_superadmin=True bo'lsa barcha bizneslarni ko'radi."""

    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='seller_profile',
    )
    business_id = models.IntegerField(
        db_index=True,
        help_text="Seller bog'langan biznes ID",
    )
    business_name = models.CharField(
        max_length=200, blank=True, default='',
    )
    is_superadmin = models.BooleanField(
        default=False,
        help_text="True bo'lsa barcha bizneslarni ko'radi (master admin)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'seller_profile'

    def __str__(self):
        return f"{self.user.username} -> Biznes #{self.business_id} ({self.business_name})"
