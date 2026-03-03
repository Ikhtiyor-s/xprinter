"""
Nonbor API dan buyurtmalarni avtomatik polling qilish.

Ishga tushirish:
    python manage.py poll_orders                  # Barcha aktiv bizneslar
    python manage.py poll_orders --business_id=96  # Faqat bitta biznes
    python manage.py poll_orders --once            # Bir marta va to'xtash
"""
import time
import logging
from django.core.management.base import BaseCommand
from printer.models import NonborConfig
from printer.services.nonbor_api import poll_and_print

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Nonbor API dan buyurtmalarni avtomatik polling qilish'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business_id',
            type=int,
            help='Faqat bitta biznes uchun polling',
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Faqat bir marta poll qilish va to\'xtash',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=0,
            help='Polling intervali (sekundlarda). 0 = configdagi qiymat',
        )

    def handle(self, *args, **options):
        business_id = options.get('business_id')
        once = options.get('once', False)
        interval_override = options.get('interval', 0)

        self.stdout.write(self.style.SUCCESS('Nonbor polling boshlandi...'))

        while True:
            # Aktiv configlarni olish
            qs = NonborConfig.objects.filter(
                is_active=True,
                poll_enabled=True,
            )
            if business_id:
                qs = qs.filter(business_id=business_id)

            configs = list(qs)

            if not configs:
                if once:
                    self.stdout.write('Aktiv polling sozlamalari topilmadi.')
                    return
                time.sleep(5)
                continue

            for config in configs:
                try:
                    new_count, printed, errors = poll_and_print(config)
                    if new_count > 0:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'[Biznes #{config.business_id}] '
                                f'{new_count} yangi, {printed} chop etildi, '
                                f'{errors} xatolik'
                            )
                        )
                except Exception as e:
                    logger.error(f'Polling xato (biznes #{config.business_id}): {e}')
                    self.stdout.write(
                        self.style.ERROR(
                            f'[Biznes #{config.business_id}] Xatolik: {e}'
                        )
                    )

            if once:
                self.stdout.write('Bir martalik polling tugadi.')
                return

            # Kutish
            sleep_time = interval_override or (configs[0].poll_interval if configs else 5)
            time.sleep(sleep_time)
