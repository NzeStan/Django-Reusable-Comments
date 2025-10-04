# Installation

This guide will help you install and set up Django Reusable Comments in your Django project.

## Requirements

Django Reusable Comments requires the following:

- Python (3.8+)
- Django (3.2+)
- Django REST Framework (3.12+)
- django-filter (21.1+)

## Installation Steps

### 1. Install the Package

You can install Django Reusable Comments using pip:

```bash
pip install django-reusable-comments
```

### 2. Add to INSTALLED_APPS

Add `django_comments` to your `INSTALLED_APPS` in your settings file:

```python
INSTALLED_APPS = [
    # ...
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    'rest_framework',
    'django_filters',
    'django_comments',
    # ...
]
```

### 3. Configure Settings

Add the configuration for Django Reusable Comments to your settings file:

```python
DJANGO_COMMENTS_CONFIG = {
    # List of model paths that can be commented on (required)
    'COMMENTABLE_MODELS': ['blog.Post', 'products.Product'],
    
    # Whether to use UUIDs for primary keys (default: False)
    'USE_UUIDS': False,
    
    # Whether moderation is required before comments are public (default: False)
    'MODERATOR_REQUIRED': False,
    
    # Maximum comment depth for threaded comments (default: 3, None = unlimited)
    'MAX_COMMENT_DEPTH': 3,
    
    # Maximum allowed length for comment content (default: 3000)
    'MAX_COMMENT_LENGTH': 3000,
    
    # Allow anonymous comments (default: True)
    'ALLOW_ANONYMOUS': True,
}
```

See the [Configuration](configuration.md) page for a complete list of available settings.

### 4. Run Migrations

Run the database migrations to create the necessary tables:

```bash
python manage.py migrate django_comments
```

### 5. Include URL Patterns

Add Django Reusable Comments' URL patterns to your project's URLconf:

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    # ...
    path('comments/', include('django_comments.urls')),
    # ...
]
```

### 6. Set Up Permissions (Optional)

If you want to use the moderation features, make sure to set up the appropriate permissions in Django's admin site or programmatically.

The package defines a custom permission `can_moderate_comments` that you can assign to users or groups.

### 7. Configure REST Framework (Optional)

If you need to customize how the REST Framework behaves with the comments API, you can add settings to your `REST_FRAMEWORK` configuration:

```python
REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}
```

## Next Steps

Once you've completed the installation, you can:

1. Check out the [Configuration](configuration.md) guide for customizing the package
2. Read the [Advanced Usage](advanced_usage.md) documentation for more complex use cases
3. Explore the [API Reference](api_reference.md) for details about the available API endpoints