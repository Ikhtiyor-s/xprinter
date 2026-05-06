import os
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv
    _env = Path(BASE_DIR) / '.env'
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass

_SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not _SECRET_KEY:
    raise RuntimeError("SECRET_KEY muhit o'zgaruvchisi o'rnatilmagan!")
SECRET_KEY = _SECRET_KEY
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0').split(',')

STATIC_ROOT    = os.path.join(BASE_DIR, 'staticfiles')
DOWNLOADS_DIR  = os.environ.get('DOWNLOADS_DIR', os.path.join(BASE_DIR, 'downloads'))

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'printer',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get('CORS_ORIGINS', 'https://printer.nonbor.uz,https://admin.nonbor.uz,http://localhost,http://localhost:80').split(',')
] if not DEBUG else []
CORS_ALLOW_CREDENTIALS = True

ROOT_URLCONF = 'urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'printer', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DB_PATH', os.path.join(BASE_DIR, 'db.sqlite3')),
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'printer.permissions.XprinterApiKeyPermission',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'auth': '5/minute',
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Webhook va API xavfsizligi
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')
XPRINTER_API_KEY = os.environ.get('XPRINTER_API_KEY', '')
