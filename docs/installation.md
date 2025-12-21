# Installation Guide

This guide walks you through installing and configuring `django-reusable-comments` in your Django project.

## Requirements

- **Python**: 3.8+
- **Django**: 3.2, 4.0, 4.1, 4.2, 5.0
- **Django REST Framework**: 3.14.0+
- **django-filter**: 23.0+
- **bleach**: 6.0.0+ (for HTML sanitization)

## Optional Dependencies

- **Markdown**: For Markdown comment formatting
- **Celery**: For async email notifications
- **Redis**: For Celery broker (if using async)

---

## Installation Steps

### 1. Install the Package

```bash
pip install django-reusable-comments
```

Or install with optional dependencies:

```bash
# For Markdown support
pip install django-reusable-comments markdown

# For async notifications
pip install django-reusable-comments celery redis
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
    path('api/comments/', include('django_comments.api.urls')),
    
    # Your app URLs
    path('', include('myapp.urls')),
]
```

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
- [ ] Include API URLs: `path('api/comments/', include('django_comments.api.urls'))`
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

## Celery Setup (Optional)

For async email notifications with Celery:

### Install Celery and Redis

```bash
pip install celery redis
```

### Configure Celery

```python
# settings.py

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Enable async notifications
DJANGO_COMMENTS_CONFIG = {
    'USE_ASYNC_NOTIFICATIONS': True,
}
```

### Create Celery App

```python
# your_project/celery.py

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')

app = Celery('your_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

### Initialize in __init__.py

```python
# your_project/__init__.py

from .celery import app as celery_app

__all__ = ('celery_app',)
```

### Start Celery Worker

```bash
celery -A your_project worker -l info
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
- [ ] Enable caching (Redis, Memcached)
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
**Solution**: Check URL configuration includes `include('django_comments.api.urls')`

**Issue**: Emails not sending
**Solution**: Check email settings and `SEND_NOTIFICATIONS = True`

**Issue**: Rate limiting not working
**Solution**: Configure DRF throttling settings

### Getting Help

- **Documentation**: [https://django-reusable-comments.readthedocs.io/](https://django-reusable-comments.readthedocs.io/)
- **Issues**: [https://github.com/NzeStan/django-reusable-comments/issues](https://github.com/NzeStan/django-reusable-comments/issues)
- **Discussions**: [https://github.com/NzeStan/django-reusable-comments/discussions](https://github.com/NzeStan/django-reusable-comments/discussions)

---

## Next Steps

After installation, check out:
- [Configuration Guide](configuration.md) - Complete settings reference
- [API Reference](api_reference.md) - REST API documentation
- [Advanced Usage](advanced_usage.md) - Advanced features and patterns
- [Contributing](contributing.md) - Contribute to the project