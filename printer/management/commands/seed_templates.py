from django.core.management.base import BaseCommand
from printer.models import IntegrationTemplate


TEMPLATES = [
    {
        'name': 'Nonbor',
        'slug': 'nonbor',
        'description': 'Nonbor POS tizimi orqali buyurtmalar',
        'icon': '🛒',
        'color': '#1890ff',
        'base_api_url': 'https://test.nonbor.uz/api/v2',
        'default_poll_interval': 5,
        'sort_order': 1,
    },
    {
        'name': 'iiko',
        'slug': 'iiko',
        'description': 'iiko restoran boshqaruv tizimi',
        'icon': '🍽️',
        'color': '#ff6b35',
        'base_api_url': '',
        'default_poll_interval': 10,
        'sort_order': 2,
    },
    {
        'name': 'R-Keeper',
        'slug': 'r-keeper',
        'description': 'R-Keeper kassa va buyurtma tizimi',
        'icon': '🏪',
        'color': '#e74c3c',
        'base_api_url': '',
        'default_poll_interval': 10,
        'sort_order': 3,
    },
    {
        'name': 'Poster',
        'slug': 'poster',
        'description': 'Poster POS tizimi integratsiyasi',
        'icon': '📋',
        'color': '#2ecc71',
        'base_api_url': '',
        'default_poll_interval': 10,
        'sort_order': 4,
    },
    {
        'name': 'Jowi',
        'slug': 'jowi',
        'description': 'Jowi restoran boshqaruv platformasi',
        'icon': '🍕',
        'color': '#9b59b6',
        'base_api_url': '',
        'default_poll_interval': 10,
        'sort_order': 5,
    },
]


class Command(BaseCommand):
    help = 'Tayyor integratsiya shablonlarini yaratish'

    def handle(self, *args, **options):
        created = 0
        for data in TEMPLATES:
            obj, is_new = IntegrationTemplate.objects.get_or_create(
                slug=data['slug'],
                defaults=data,
            )
            if is_new:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  + {obj.name}'))
            else:
                self.stdout.write(f'  = {obj.name} (allaqachon mavjud)')
        self.stdout.write(self.style.SUCCESS(f'Jami: {created} ta yangi shablon yaratildi'))
