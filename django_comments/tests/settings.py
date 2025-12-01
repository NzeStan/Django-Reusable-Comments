"""
Settings file for running the tests.
"""
import os

SECRET_KEY = 'django-comments-tests-secret-key'
DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_filters',
    'django_comments',
    'django_comments.tests',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'django_comments.tests.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# Django Comments settings
# FIXED: Use the correct app_label for test models
DJANGO_COMMENTS_CONFIG = {
    # The app_label for models in django_comments/tests/models.py is 'tests'
    # Model name is case-insensitive in Django
    'COMMENTABLE_MODELS': [
        'tests.testpost',           # Main test model
        'tests.testpostwithuuid',   # UUID test model
    ],
    'USE_UUIDS': False,
    'MODERATOR_REQUIRED': False,
    'ALLOW_ANONYMOUS': True,
    'MAX_COMMENT_DEPTH': 3,
    'MAX_COMMENT_LENGTH': 3000,
}

# For development - use database cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'comment_cache_table',
    }
}

# Optional: Configure cache timeout
DJANGO_COMMENTS_CONFIG = {
    # ... your existing settings ...
    'CACHE_TIMEOUT': 3600,  # 1 hour
}