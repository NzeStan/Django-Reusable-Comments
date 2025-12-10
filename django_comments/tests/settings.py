"""
Django settings for running django_comments tests.

This settings file is specifically configured for testing and includes:
- In-memory SQLite database for fast tests
- All required Django apps
- REST Framework configuration
- Comment system settings
- Security settings for test environment
"""
import os
import sys
from pathlib import Path

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security settings (test environment)
SECRET_KEY = 'django-comments-test-secret-key-not-for-production-use'
DEBUG = True
ALLOWED_HOSTS = ['*']

# Database
# Use in-memory SQLite for fast tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': True,
    }
}

# Installed applications
INSTALLED_APPS = [
    # Django core apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required for notifications
    
    # Third-party apps
    'rest_framework',
    'django_filters',
    
    # Our app
    'django_comments',
    
    # Test app (provides TestPost and TestPostWithUUID models)
    'django_comments.tests',
]

# Site ID for django.contrib.sites
SITE_ID = 1

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# URL configuration
ROOT_URLCONF = 'django_comments.tests.urls'

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'django_comments', 'templates'),
        ],
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

# Password validation (simplified for tests)
AUTH_PASSWORD_VALIDATORS = []

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================================
# REST Framework Configuration
# ============================================================================

REST_FRAMEWORK = {
    # Authentication
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    
    # Permissions
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    
    # Filtering
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    
    # Pagination
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    
    # Rendering
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    
    # Parsing
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    
    # Throttling (disabled for tests)
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {
        'anon': None,
        'user': None,
    },
    
    # Exception handling
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
    
    # Datetime formatting
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S.%fZ',
    'DATETIME_INPUT_FORMATS': ['%Y-%m-%dT%H:%M:%S.%fZ', 'iso-8601'],
    
    # Testing
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
}

# ============================================================================
# Django Comments Configuration
# ============================================================================

DJANGO_COMMENTS_CONFIG = {
    # Commentable models
    'COMMENTABLE_MODELS': [
        'django_comments.tests.models.TestPost',
        'django_comments.tests.models.TestPostWithUUID',
    ],
    
    # Moderation settings
    'ENABLE_MODERATION': True,
    'AUTO_APPROVE_COMMENTS': False,
    'ENABLE_PROFANITY_FILTER': True,
    'ENABLE_SPAM_DETECTION': True,
    
    # Flag settings
    'MAX_FLAGS_PER_USER': 5,
    'AUTO_HIDE_THRESHOLD': 3,
    
    # Threading settings
    'ENABLE_THREADING': True,
    'MAX_THREAD_LEVEL': 10,
    
    # Anonymous comments
    'ALLOW_ANONYMOUS_COMMENTS': True,
    
    # Email notifications
    'SEND_NOTIFICATIONS': False,  # Disabled for tests
    
    # Rate limiting
    'ENABLE_RATE_LIMITING': False,  # Disabled for tests
    
    # Akismet spam detection
    'AKISMET_API_KEY': None,  # Not used in tests
    
    # Profanity filter
    'PROFANITY_WORDS': [
        'badword1',
        'badword2',
        'inappropriate',
    ],
    
    # Comment length limits
    'MIN_COMMENT_LENGTH': 1,
    'MAX_COMMENT_LENGTH': 5000,
    
    # User fields for anonymous comments
    'REQUIRE_NAME_EMAIL': True,
    
    # IP tracking
    'TRACK_IP_ADDRESSES': True,
}

# ============================================================================
# Logging Configuration (minimal for tests)
# ============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django_comments': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# ============================================================================
# Cache Configuration (in-memory for tests)
# ============================================================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}

# ============================================================================
# Email Configuration (console backend for tests)
# ============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'test@example.com'

# ============================================================================
# Security Settings (relaxed for tests)
# ============================================================================

# CSRF
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = False

# Session
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Security headers
SECURE_SSL_REDIRECT = False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ============================================================================
# Testing-specific settings
# ============================================================================

# Password hashers (fast for testing)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable migrations for faster tests (optional)
# Uncomment if you want even faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Test runner
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# Celery (if used, disable for tests)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ============================================================================
# Custom settings for specific test scenarios
# ============================================================================

# Flag to check if we're running tests
TESTING = True

# Additional test-specific configurations
TEST_COMMENT_MAX_LENGTH = 5000
TEST_ENABLE_QUERY_LOGGING = False  # Set to True to debug query issues

# Feature flags for testing different configurations
FEATURES = {
    'ENABLE_THREADING': True,
    'ENABLE_MODERATION': True,
    'ENABLE_FLAGS': True,
    'ENABLE_ANONYMOUS_COMMENTS': True,
}