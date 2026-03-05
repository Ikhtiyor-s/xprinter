"""
Printer xatolik bildirishnomalari servisi.
Telegram va DB ga xabar yuborish.
"""
import logging
from datetime import timedelta

import requests
from django.utils import timezone

from ..models import PrintJob, PrinterNotification, NotificationConfig, NonborConfig

logger = logging.getLogger(__name__)


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Telegram Bot API orqali xabar yuborish."""
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(url, json={
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML',
        }, timeout=10)
        if resp.status_code == 200:
            return True
        logger.warning(f"Telegram xabar yuborib bo'lmadi: {resp.status_code}")
        return False
    except Exception as e:
        logger.error(f"Telegram xabar xatolik: {e}")
        return False


def notify_print_failure(job: PrintJob, error: str):
    """Print job xatolikda — DB ga saqlash + Telegram yuborish."""
    business_id = job.business_id
    printer_name = job.printer.name if job.printer_id else "Noma'lum"
    order_id = job.order_id

    # Spam oldini olish: oxirgi 60s da shu printer uchun xabar borganmi?
    recent = PrinterNotification.objects.filter(
        business_id=business_id,
        printer_name=printer_name,
        created_at__gte=timezone.now() - timedelta(seconds=60),
    ).exists()

    # Biznes nomini olish
    business_name = ''
    try:
        nc = NonborConfig.objects.filter(business_id=business_id).first()
        if nc:
            business_name = nc.business_name or ''
    except Exception:
        pass

    # 1. DB ga bildirishnoma saqlash
    title = f"Printer xatolik: {printer_name}"
    message_text = (
        f"Buyurtma #{order_id} chop etilmadi.\n"
        f"Printer: {printer_name}\n"
        f"Xatolik: {error}\n"
        f"Urinish: {job.retry_count}/{job.max_retries}"
    )

    notification = PrinterNotification.objects.create(
        business_id=business_id,
        business_name=business_name,
        printer_name=printer_name,
        order_id=order_id,
        print_job_id=job.id,
        level=PrinterNotification.LEVEL_ERROR,
        title=title,
        message=message_text,
    )

    # 2. Telegram ga xabar (agar sozlangan va spam emas)
    if not recent:
        try:
            config = NotificationConfig.objects.get(
                business_id=business_id,
                is_active=True,
                telegram_enabled=True,
            )
        except NotificationConfig.DoesNotExist:
            config = None

        if config and config.telegram_bot_token and config.telegram_chat_id:
            telegram_text = (
                f"\U0001f534 <b>Printer xatolik!</b>\n\n"
                f"\U0001f4cb Buyurtma: <b>#{order_id}</b>\n"
                f"\U0001f5a8 Printer: <b>{printer_name}</b>\n"
                f"\u274c Xatolik: {error}\n"
                f"\U0001f504 Urinish: {job.retry_count}/{job.max_retries}\n"
                f"\U0001f550 Vaqt: {timezone.now().strftime('%H:%M:%S')}"
            )
            sent = send_telegram_message(
                config.telegram_bot_token,
                config.telegram_chat_id,
                telegram_text,
            )
            if sent:
                notification.telegram_sent = True
                notification.save(update_fields=['telegram_sent'])

    return notification


def check_cloud_timeouts():
    """Cloud printer joblarni tekshirish — pending X daqiqadan oshsa failed."""
    configs = NotificationConfig.objects.filter(is_active=True)
    timeout_map = {c.business_id: c.cloud_timeout_minutes for c in configs}
    default_timeout = 5

    stale_jobs = PrintJob.objects.filter(
        status=PrintJob.STATUS_PENDING,
        printer__connection_type='cloud',
    ).select_related('printer')

    now = timezone.now()
    timed_out = 0

    for job in stale_jobs:
        timeout_min = timeout_map.get(job.business_id, default_timeout)
        deadline = job.created_at + timedelta(minutes=timeout_min)

        if now > deadline:
            error = (
                f"Cloud printer javob bermadi "
                f"({timeout_min} daqiqa). Agent offline bo'lishi mumkin."
            )
            job.mark_failed(error)
            notify_print_failure(job, error)
            timed_out += 1
            logger.warning(
                f"Cloud timeout: Job #{job.id}, Order #{job.order_id}, "
                f"Printer: {job.printer.name}"
            )

    return timed_out
