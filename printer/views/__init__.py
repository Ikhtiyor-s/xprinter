from .printer import PrinterDetectView, PrinterCreateView, PrinterListView, PrinterDetailView, PrinterUpdateView, PrinterDeleteView, PrinterTestPrintView  # noqa
from .category import PrinterCategoryAssignView, PrinterCategoryListView, PrinterCategoryRemoveView, PrinterCategoryBulkAssignView, PrinterCategoryByPrinterView  # noqa
from .product import PrinterProductAssignView, PrinterProductListView, PrinterProductRemoveView, PrinterProductBulkAssignView, PrinterProductByPrinterView  # noqa
from .print_job import PrintJobListView, PrintJobRetryView, PrintOrderView  # noqa
from .agent import AgentPollView, AgentCompleteView, PrinterAgentSyncView  # noqa
from .agent_creds import AgentAuthView, NonborMenuView, AgentCredentialListView, AgentCredentialCreateView, AgentCredentialUpdateView, AgentCredentialDeleteView  # noqa
from .nonbor import NonborConfigCreateView, NonborConfigListView, NonborConfigDetailView, NonborConfigUpdateView, NonborConfigDeleteView, NonborPollView, NonborOrdersView, NonborPollStartView, NonborPollStopView, NonborPollAllView  # noqa
from .order_service import OrderServiceListView, OrderServiceCreateView, OrderServiceUpdateView, OrderServiceDeleteView  # noqa
from .integration import IntegrationTemplateListView, IntegrationTemplateCreateView, IntegrationTemplateUpdateView, IntegrationTemplateDeleteView  # noqa
from .receipt import ReceiptTemplateListView, ReceiptTemplateDetailView, ReceiptTemplateSaveView, ReceiptTemplateDeleteView  # noqa
from .webhook import PrintWebhookView  # noqa
from .notification import NotificationListView, NotificationUnreadCountView, NotificationMarkReadView, NotificationConfigSaveView, NotificationConfigDetailView, NotificationTestTelegramView  # noqa
from .auth import AdminTokenLoginView, AdminTokenLogoutView  # noqa
from .health import HealthCheckView  # noqa
from .dashboard import agent_dashboard  # noqa
