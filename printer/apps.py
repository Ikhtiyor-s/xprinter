import threading
import time
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class PrinterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'printer'
    verbose_name = 'Xprinter boshqarish'

    def ready(self):
        # Django ishga tushganda avtomatik polling boshlash
        # manage.py migrate, makemigrations kabi commandlarda ishlamasin
        import sys
        if 'runserver' in sys.argv:
            self._start_polling_thread()

    def _start_polling_thread(self):
        """Background threadda Nonbor API polling"""
        thread = threading.Thread(
            target=self._polling_loop,
            name='nonbor-poller',
            daemon=True,
        )
        thread.start()
        logger.info("Nonbor polling thread boshlandi")

    def _polling_loop(self):
        """Doimiy polling loop"""
        # Django to'liq yuklanguncha kutish
        time.sleep(5)

        from printer.models import NonborConfig
        from printer.services.nonbor_api import poll_and_print

        logger.info("Nonbor polling loop ishlamoqda...")

        while True:
            try:
                configs = NonborConfig.objects.filter(
                    is_active=True,
                    poll_enabled=True,
                )
                for config in configs:
                    try:
                        new_count, printed, errors = poll_and_print(config)
                        if new_count > 0:
                            logger.info(
                                f"[Biznes #{config.business_id}] "
                                f"{new_count} yangi buyurtma, "
                                f"{printed} chop etildi"
                            )
                    except Exception as e:
                        logger.error(
                            f"Polling xato (biznes #{config.business_id}): {e}"
                        )
            except Exception as e:
                logger.error(f"Polling loop xato: {e}")

            time.sleep(5)  # Har 5 soniyada tekshiramiz
