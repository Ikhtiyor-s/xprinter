from django.contrib import admin
from .models import Printer, PrinterCategory, PrinterProduct, PrintJob


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
