"""
Minimal Django settings for running django-reusable-comments tests.

Usage:
    pytest                                   # pyproject.toml sets this automatically
    DJANGO_SETTINGS_MODULE=django_comments.tests.settings pytest
    python -m pytest
"""

SECRET_KEY = "django-insecure-test-secret-key-for-testing-only"

DEBUG = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "rest_framework",
    "django_filters",
    "django_comments",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Use Django's built-in database cache backend (no Redis/Memcached required)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache_table",
    }
}

# Use in-memory cache for tests to avoid needing a real cache table
# Override CACHES to use LocMemCache for test isolation
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

SITE_ID = 1

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email — capture all outbound mail in memory so tests can inspect it
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@example.com"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
}

USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"

DJANGO_COMMENTS_CONFIG = {
    # Allow all models to be commented on during tests
    "COMMENTABLE_MODELS": [],
    # Disable async notifications in tests — tasks run synchronously
    "USE_ASYNC_NOTIFICATIONS": False,
    # Keep notifications off by default; individual tests override as needed
    "SEND_NOTIFICATIONS": False,
}
