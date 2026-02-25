# Installation Guide

This guide walks you through installing and configuring `django-reusable-comments` in your Django project.

## Requirements

- **Python**: 3.8, 3.9, 3.10, 3.11, 3.12
- **Django**: 3.2, 4.0, 4.1, 4.2, 5.0
- **Django REST Framework**: 3.14.0+
- **django-filter**: 23.0+
- **bleach**: 6.0.0+ (for HTML sanitization)

## Optional Dependencies

- **Markdown**: For Markdown comment formatting (`pip install markdown`)

No external task queue or message broker is required. Async email notifications are handled via Python's built-in `threading` module.

See `requirements.txt` for production dependencies and `requirements-dev.txt` for development dependencies.

---

## Installation Steps

### 1. Install the Package

```bash
pip install django-reusable-comments
```

Or install with optional Markdown support:

```bash
# For Markdown support
pip install django-reusable-comments markdown
```

### 2. Add to INSTALLED_APPS

Add the app and its dependencies to your `INSTALLED_APPS`:

```python
# settings.py

INSTALLED_APPS = [
    # Django built-in apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'django_filters',

    # Django Reusable Comments
    'django_comments',

    # Your apps
    'myapp',
]
```

### 3. Configure URLs

Add the comment URLs to your project's URL configuration:
```python
# urls.py

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Django Reusable Comments API
    # Provides TWO endpoint patterns:
    # 1. Generic: /api/comments/ (full CRUD)
    # 2. Object-specific: /api/{app_label}/{model}/{object_id}/comments/ (secure create/list)
    path('api/', include('django_comments.urls')),

    # Your app URLs
    path('', include('myapp.urls')),
]
```

This configuration enables:
- **Generic endpoint**: `/api/comments/` for full CRUD operations
- **Object-specific endpoint**: `/api/{app_label}/{model}/{object_id}/comments/` for secure comment creation

**Example URLs**:

### 4. Run Migrations

Create the database tables for comments:

```bash
python manage.py migrate django_comments
```

This creates the following tables:
- `django_comments_comment` - Main comment table
- `django_comments_commentflag` - Comment flags (spam, inappropriate, etc.)
- `django_comments_banneduser` - Banned users
- `django_comments_commentrevision` - Edit history
- `django_comments_moderationaction` - Moderation logs

### 5. Basic Configuration

Add basic configuration to your settings:

```python
# settings.py

DJANGO_COMMENTS_CONFIG = {
    # Which models can be commented on
    'COMMENTABLE_MODELS': [
        'blog.Post',
        'products.Product',
    ],

    # Moderation
    'MODERATOR_REQUIRED': False,  # Set to True for approval workflow

    # Threading
    'MAX_COMMENT_DEPTH': 3,  # Maximum reply depth

    # Content
    'MAX_COMMENT_LENGTH': 3000,
    'ALLOW_ANONYMOUS': False,
    'COMMENT_FORMAT': 'plain',  # 'plain', 'markdown', or 'html'

    # Notifications
    'SEND_NOTIFICATIONS': True,

    # API
    'API_RATE_LIMIT': '100/day',
    'API_RATE_LIMIT_ANON': '20/day',
}
```

---

## Quick Start Checklist

- [ ] Install package: `pip install django-reusable-comments`
- [ ] Add `'django_comments'` to `INSTALLED_APPS`
- [ ] Add `'rest_framework'` and `'django_filters'` to `INSTALLED_APPS`
- [ ] Include API URLs: `path('api/', include('django_comments.urls'))`
- [ ] Run migrations: `python manage.py migrate django_comments`
- [ ] Configure commentable models in `DJANGO_COMMENTS_CONFIG`
- [ ] Test API endpoint: `GET /api/comments/`

---

## Email Configuration (Optional)

If you want to enable email notifications:

```python
# settings.py

# Django email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'noreply@yourdomain.com'

# Comments notification settings
DJANGO_COMMENTS_CONFIG = {
    'SEND_NOTIFICATIONS': True,
    'COMMENT_NOTIFICATION_EMAILS': ['moderators@yourdomain.com'],
}
```

---

## Async Notifications (Built-in Threading)

Async email notifications are built in — no Celery, Redis, or external broker required. When enabled, each notification is dispatched to a Python daemon thread so the HTTP request returns immediately.

Failures are logged (not retried). For guaranteed delivery in high-volume production environments, wrap calls in a persistent task queue of your choice.

### Enable Async Notifications

```python
# settings.py

DJANGO_COMMENTS_CONFIG = {
    'SEND_NOTIFICATIONS': True,
    'USE_ASYNC_NOTIFICATIONS': True,  # Uses Python threading (no broker needed)
}
```

That's all — no worker processes to start, no broker to configure.

---

## Caching Setup (Optional)

django-reusable-comments uses Django's cache framework for comment counts and other frequently accessed data.

### Default (LocMemCache)

Django's default in-process memory cache works out of the box for development and small deployments.

### Recommended: Database Cache

For multi-process production deployments (e.g., multiple gunicorn workers), use Django's built-in database cache so all workers share the same cache:

```bash
# Create the cache table (once)
python manage.py createcachetable
```

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache',
    }
}
```

No external services required.

### Memcached or Redis (Optional)

You can use Memcached or Redis if they are already in your stack:

```python
# Memcached
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION': '127.0.0.1:11211',
    }
}

# Redis (requires django-redis)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

---

## REST Framework Configuration

django-reusable-comments integrates with Django REST Framework. Here's a recommended DRF configuration:

```python
# settings.py

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
    },
}
```

---

## Production Checklist

Before deploying to production:

### Security
- [ ] Set `DEBUG = False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Enable HTTPS
- [ ] Set strong `SECRET_KEY`
- [ ] Enable CSRF protection
- [ ] Configure CORS headers

### Comments Configuration
- [ ] Enable moderation: `'MODERATOR_REQUIRED': True`
- [ ] Enable spam detection: `'SPAM_DETECTION_ENABLED': True`
- [ ] Enable profanity filtering: `'PROFANITY_FILTERING': True`
- [ ] Configure auto-moderation thresholds
- [ ] Set up email notifications
- [ ] Configure GDPR compliance
- [ ] Set appropriate rate limits

### Database
- [ ] Use production database (PostgreSQL, MySQL)
- [ ] Run migrations
- [ ] Set up database backups
- [ ] Configure connection pooling

### Performance
- [ ] Enable caching (database cache, Memcached, or Redis)
- [ ] Configure static files serving
- [ ] Set up CDN for media files
- [ ] Enable database query optimization
- [ ] Configure proper logging

### Monitoring
- [ ] Set up error tracking (Sentry, etc.)
- [ ] Configure logging
- [ ] Set up performance monitoring
- [ ] Enable health checks

---

## Testing Your Installation

### 1. Check Admin Interface

Visit `/admin/` and verify you can see:
- Comments
- Comment Flags
- Banned Users
- Comment Revisions
- Moderation Actions

### 2. Test API Endpoints

```bash
# List comments
curl http://localhost:8000/api/comments/

# Create a comment (authenticated)
curl -X POST http://localhost:8000/api/comments/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token YOUR_TOKEN" \
  -d '{
    "content_type": "blog.post",
    "object_id": "1",
    "content": "Test comment"
  }'
```

### 3. Test Template Tags

Create a test template:

```django
{% load comment_tags %}

{# Get comment count #}
{% get_comment_count article as comment_count %}
<p>{{ comment_count }} comments</p>

{# List comments #}
{% get_comments article as comments %}
{% for comment in comments %}
  <div class="comment">
    <strong>{{ comment.user.username }}</strong>
    <p>{{ comment.content }}</p>
  </div>
{% endfor %}
```

---

## Troubleshooting

### Common Issues

**Issue**: `ImportError: cannot import name 'django_comments'`
**Solution**: Ensure the package is installed and added to `INSTALLED_APPS`

**Issue**: `No module named 'rest_framework'`
**Solution**: Install Django REST Framework: `pip install djangorestframework`

**Issue**: Migrations not running
**Solution**: Make sure app name is `'django_comments'` (with underscore, not hyphen)

**Issue**: API returns 404
**Solution**: Check URL configuration includes `include('django_comments.urls')`

**Issue**: Emails not sending
**Solution**: Check email settings and `SEND_NOTIFICATIONS = True`

**Issue**: Rate limiting not working
**Solution**: Configure DRF throttling settings

### Getting Help

- **Documentation**: [https://github.com/NzeStan/django-reusable-comments/blob/main/docs/installation.md](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/installation.md)
- **Issues**: [https://github.com/NzeStan/django-reusable-comments/issues](https://github.com/NzeStan/django-reusable-comments/issues)
- **Discussions**: [https://github.com/NzeStan/django-reusable-comments/discussions](https://github.com/NzeStan/django-reusable-comments/discussions)

---

## Next Steps

After installation, check out:
- [Configuration Guide](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/configuration.md) - Complete settings reference
- [API Reference](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/api_reference.md) - REST API documentation
- [Advanced Usage](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/advanced_usage.md) - Advanced features and patterns
- [Contributing](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/contributing.md) - Contribute to the project
