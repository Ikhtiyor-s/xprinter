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
        """Markaziy polling loop — bir xil API URL uchun BITTA so'rov"""
        # Django to'liq yuklanguncha kutish
        time.sleep(5)

        from printer.models import NonborConfig
        from printer.services.nonbor_api import poll_and_print, fetch_all_orders

        logger.info("Markaziy polling loop ishlamoqda...")

        while True:
            try:
                configs = list(NonborConfig.objects.filter(
                    is_active=True,
                    poll_enabled=True,
                ))

                if not configs:
                    time.sleep(5)
                    continue

                # Configlarni (api_url, api_secret) bo'yicha guruhlash
                groups = {}
                for config in configs:
                    key = (config.api_url, config.api_secret)
                    groups.setdefault(key, []).append(config)

                # Har bir unikal URL uchun BITTA so'rov
                for (api_url, api_secret), group_configs in groups.items():
                    try:
                        all_orders = fetch_all_orders(api_url, api_secret)
                        biz_ids = [c.business_id for c in group_configs]
                        logger.debug(
                            f"Markaziy polling: 1 so'rov -> {len(all_orders)} buyurtma, "
                            f"{len(group_configs)} config ({biz_ids})"
                        )

                        # Har bir config uchun buyurtmalarni filtrlab berish
                        for config in group_configs:
                            try:
                                new_count, printed, errors = poll_and_print(
                                    config, orders=all_orders
                                )
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
                        logger.error(f"Markaziy polling xato ({api_url}): {e}")

            except Exception as e:
                logger.error(f"Polling loop xato: {e}")

            time.sleep(5)  # Har 5 sekundda tekshiramiz
