from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Printer, PrinterCategory, PrinterProduct, PrintJob, NotificationConfig, PrinterNotification, SellerProfile, AgentCredential, NonborConfig


class PrinterCategoryInline(admin.TabularInline):
    model = PrinterCategory
    extra = 1
    fields = ['category_id', 'category_name', 'business_id']


class PrinterProductInline(admin.TabularInline):
    model = PrinterProduct
    extra = 1
    fields = ['product_id', 'product_name', 'business_id']


@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'business_id', 'connection_type',
        'ip_address', 'port', 'printer_model',
        'paper_width', 'is_active', 'auto_print',
    ]
    list_filter = ['connection_type', 'is_active', 'auto_print', 'paper_width']
    search_fields = ['name', 'ip_address', 'printer_model']
    list_editable = ['is_active', 'auto_print']
    inlines = [PrinterCategoryInline, PrinterProductInline]


@admin.register(PrinterCategory)
class PrinterCategoryAdmin(admin.ModelAdmin):
    list_display = ['printer', 'category_id', 'category_name', 'business_id']
    list_filter = ['business_id']
    search_fields = ['category_name']


@admin.register(PrinterProduct)
class PrinterProductAdmin(admin.ModelAdmin):
    list_display = ['printer', 'product_id', 'product_name', 'business_id']
    list_filter = ['business_id', 'printer']
    search_fields = ['product_name']


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'printer', 'order_id', 'business_id',
        'status', 'retry_count', 'created_at', 'printed_at',
    ]
    list_filter = ['status', 'business_id', 'printer']
    search_fields = ['order_id']
    readonly_fields = ['content', 'items_data', 'error_message', 'created_at', 'printed_at']
    date_hierarchy = 'created_at'


@admin.register(NotificationConfig)
class NotificationConfigAdmin(admin.ModelAdmin):
    list_display = ['business_id', 'business_name', 'telegram_enabled', 'cloud_timeout_seconds', 'is_active']
    list_filter = ['telegram_enabled', 'is_active']


@admin.register(PrinterNotification)
class PrinterNotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'business_id', 'printer_name', 'order_id', 'level', 'title', 'is_read', 'telegram_sent', 'created_at']
    list_filter = ['level', 'is_read', 'telegram_sent']
    date_hierarchy = 'created_at'


# SellerProfile — User bilan inline
class SellerProfileInline(admin.StackedInline):
    model = SellerProfile
    can_delete = False
    verbose_name = 'Seller profili'
    verbose_name_plural = 'Seller profili'
    fields = ['business_id', 'business_name', 'is_superadmin']


# User admin ga SellerProfile inline qo'shish
class CustomUserAdmin(BaseUserAdmin):
    inlines = [SellerProfileInline]
    list_display = ['username', 'email', 'is_staff', 'is_active', 'get_business_id']

    def get_business_id(self, obj):
        try:
            return obj.seller_profile.business_id
        except SellerProfile.DoesNotExist:
            return '-'
    get_business_id.short_description = 'Business ID'


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'business_id', 'business_name', 'is_superadmin']
    list_filter = ['is_superadmin']
    search_fields = ['user__username', 'business_name']


@admin.register(AgentCredential)
class AgentCredentialAdmin(admin.ModelAdmin):
    list_display = ['username', 'business_id', 'business_name', 'is_active']
    list_filter = ['is_active', 'business_id']
    search_fields = ['username', 'business_name']


@admin.register(NonborConfig)
class NonborConfigAdmin(admin.ModelAdmin):
    list_display = ['business_id', 'business_name', 'api_url', 'poll_enabled', 'is_active']
    list_filter = ['poll_enabled', 'is_active']
