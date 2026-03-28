from django.urls import path
from . import views

urlpatterns = [
    # ============================================================
    # PRINTER CRUD
    # ============================================================
    path('printer/detect/', views.PrinterDetectView.as_view(), name='printer-detect'),
    path('printer/create/', views.PrinterCreateView.as_view(), name='printer-create'),
    path('printer/list/', views.PrinterListView.as_view(), name='printer-list'),
    path('printer/<int:pk>/detail/', views.PrinterDetailView.as_view(), name='printer-detail'),
    path('printer/<int:pk>/update/', views.PrinterUpdateView.as_view(), name='printer-update'),
    path('printer/<int:pk>/delete/', views.PrinterDeleteView.as_view(), name='printer-delete'),
    path('printer/<int:pk>/test-print/', views.PrinterTestPrintView.as_view(), name='printer-test'),

    # ============================================================
    # PRINTER CATEGORY MAPPING
    # ============================================================
    path('printer-category/assign/', views.PrinterCategoryAssignView.as_view(), name='printer-cat-assign'),
    path('printer-category/list/', views.PrinterCategoryListView.as_view(), name='printer-cat-list'),
    path('printer-category/<int:pk>/remove/', views.PrinterCategoryRemoveView.as_view(), name='printer-cat-remove'),
    path('printer-category/bulk-assign/', views.PrinterCategoryBulkAssignView.as_view(), name='printer-cat-bulk'),
    path('printer-category/by-printer/<int:printer_id>/', views.PrinterCategoryByPrinterView.as_view(), name='printer-cat-by-printer'),

    # ============================================================
    # PRINTER PRODUCT MAPPING
    # ============================================================
    path('printer-product/assign/', views.PrinterProductAssignView.as_view(), name='printer-prod-assign'),
    path('printer-product/list/', views.PrinterProductListView.as_view(), name='printer-prod-list'),
    path('printer-product/<int:pk>/remove/', views.PrinterProductRemoveView.as_view(), name='printer-prod-remove'),
    path('printer-product/bulk-assign/', views.PrinterProductBulkAssignView.as_view(), name='printer-prod-bulk'),
    path('printer-product/by-printer/<int:printer_id>/', views.PrinterProductByPrinterView.as_view(), name='printer-prod-by-printer'),

    # ============================================================
    # PRINT JOB
    # ============================================================
    path('print-job/list/', views.PrintJobListView.as_view(), name='printjob-list'),
    path('print-job/<int:pk>/retry/', views.PrintJobRetryView.as_view(), name='printjob-retry'),
    path('print-job/print-order/<int:order_id>/', views.PrintOrderView.as_view(), name='printjob-print-order'),
    path('print-job/webhook/', views.PrintWebhookView.as_view(), name='printjob-webhook'),

    # ============================================================
    # PRINT AGENT (masofadan chop etish)
    # ============================================================
    path('print-job/agent/poll/', views.AgentPollView.as_view(), name='agent-poll'),
    path('print-job/agent/complete/', views.AgentCompleteView.as_view(), name='agent-complete'),
    path('agent/auth/', views.AgentAuthView.as_view(), name='agent-auth'),
    path('agent/menu/<int:business_id>/', views.NonborMenuView.as_view(), name='agent-menu'),
    path('agent/printer-sync/', views.PrinterAgentSyncView.as_view(), name='agent-printer-sync'),

    # ============================================================
    # NONBOR CONFIG (API sozlamalari)
    # ============================================================
    path('nonbor-config/create/', views.NonborConfigCreateView.as_view(), name='nonbor-config-create'),
    path('nonbor-config/list/', views.NonborConfigListView.as_view(), name='nonbor-config-list'),
    path('nonbor-config/<int:business_id>/detail/', views.NonborConfigDetailView.as_view(), name='nonbor-config-detail'),
    path('nonbor-config/<int:business_id>/update/', views.NonborConfigUpdateView.as_view(), name='nonbor-config-update'),
    path('nonbor-config/<int:business_id>/delete/', views.NonborConfigDeleteView.as_view(), name='nonbor-config-delete'),

    # ============================================================
    # AGENT CREDENTIAL CRUD (Print Agent login/parol)
    # ============================================================
    path('agent-credential/list/', views.AgentCredentialListView.as_view(), name='agent-cred-list'),
    path('agent-credential/create/', views.AgentCredentialCreateView.as_view(), name='agent-cred-create'),
    path('agent-credential/<int:pk>/update/', views.AgentCredentialUpdateView.as_view(), name='agent-cred-update'),
    path('agent-credential/<int:pk>/delete/', views.AgentCredentialDeleteView.as_view(), name='agent-cred-delete'),

    # ============================================================
    # ORDER SERVICE CRUD (Tashqi servislar)
    # ============================================================
    path('order-service/list/', views.OrderServiceListView.as_view(), name='order-service-list'),
    path('order-service/create/', views.OrderServiceCreateView.as_view(), name='order-service-create'),
    path('order-service/<int:pk>/update/', views.OrderServiceUpdateView.as_view(), name='order-service-update'),
    path('order-service/<int:pk>/delete/', views.OrderServiceDeleteView.as_view(), name='order-service-delete'),

    # ============================================================
    # INTEGRATION TEMPLATE (Integratsiya shablonlari)
    # ============================================================
    path('integration-template/list/', views.IntegrationTemplateListView.as_view(), name='integration-template-list'),
    path('integration-template/create/', views.IntegrationTemplateCreateView.as_view(), name='integration-template-create'),
    path('integration-template/<int:pk>/update/', views.IntegrationTemplateUpdateView.as_view(), name='integration-template-update'),
    path('integration-template/<int:pk>/delete/', views.IntegrationTemplateDeleteView.as_view(), name='integration-template-delete'),

    # ============================================================
    # RECEIPT TEMPLATE (Chek shablonlari)
    # ============================================================
    path('receipt-template/list/', views.ReceiptTemplateListView.as_view(), name='receipt-template-list'),
    path('receipt-template/<int:business_id>/detail/', views.ReceiptTemplateDetailView.as_view(), name='receipt-template-detail'),
    path('receipt-template/save/', views.ReceiptTemplateSaveView.as_view(), name='receipt-template-save'),
    path('receipt-template/<int:business_id>/delete/', views.ReceiptTemplateDeleteView.as_view(), name='receipt-template-delete'),

    # ============================================================
    # NONBOR POLLING (avtomatik buyurtma olish)
    # ============================================================
    path('nonbor/poll-all/', views.NonborPollAllView.as_view(), name='nonbor-poll-all'),
    path('nonbor/poll/<int:business_id>/', views.NonborPollView.as_view(), name='nonbor-poll'),
    path('nonbor/orders/<int:business_id>/', views.NonborOrdersView.as_view(), name='nonbor-orders'),
    path('nonbor/poll-start/<int:business_id>/', views.NonborPollStartView.as_view(), name='nonbor-poll-start'),
    path('nonbor/poll-stop/<int:business_id>/', views.NonborPollStopView.as_view(), name='nonbor-poll-stop'),

    # ============================================================
    # ADMIN AUTH (token login/logout)
    # ============================================================
    path('admin/login/', views.AdminTokenLoginView.as_view(), name='admin-login'),
    path('admin/logout/', views.AdminTokenLogoutView.as_view(), name='admin-logout'),

    # ============================================================
    # NOTIFICATIONS (Printer xatolik bildirishnomalari)
    # ============================================================
    path('notification/list/', views.NotificationListView.as_view(), name='notification-list'),
    path('notification/unread-count/', views.NotificationUnreadCountView.as_view(), name='notification-unread-count'),
    path('notification/mark-read/', views.NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('notification-config/save/', views.NotificationConfigSaveView.as_view(), name='notification-config-save'),
    path('notification-config/<int:business_id>/detail/', views.NotificationConfigDetailView.as_view(), name='notification-config-detail'),
    path('notification-config/test-telegram/', views.NotificationTestTelegramView.as_view(), name='notification-test-telegram'),
]
