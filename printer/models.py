from django.db import models
from django.utils import timezone


class Printer(models.Model):
    """Oshxona printeri - har bir biznesda bir nechta printer bo'lishi mumkin"""

    CONNECTION_NETWORK = 'network'
    CONNECTION_USB = 'usb'
    CONNECTION_CLOUD = 'cloud'
    CONNECTION_CHOICES = [
        (CONNECTION_NETWORK, 'Tarmoq (IP) - lokal'),
        (CONNECTION_USB, 'USB - lokal'),
        (CONNECTION_CLOUD, 'Cloud - masofadan (agent orqali)'),
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
        conn = self.ip_address if self.connection_type == self.CONNECTION_NETWORK else self.usb_path
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
        default='https://test.nonbor.uz/api/v2',
        help_text="Nonbor API URL"
    )
    api_secret = models.CharField(
        max_length=200,
        default='nonbor-secret-key',
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
        help_text="Agent parol (sodda matn)"
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

    def check_password(self, raw: str) -> bool:
        return self.password == raw


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
        help_text="Nonbor order ID"
    )
    business_id = models.IntegerField(db_index=True)
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
