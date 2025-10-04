# Django Reusable Comments

A professional-grade, reusable Django app for adding comment functionality to any model in your Django project.

## Features

- ✅ **Model Agnostic** - Add comments to any Django model
- ✅ **ID Flexibility** - Support for both UUID and integer primary keys
- ✅ **Highly Customizable** - Extensive settings and configuration options
- ✅ **Signals** - Robust signal system for extending functionality
- ✅ **Internationalization** - Full i18n support using gettext_lazy
- ✅ **DRF Integration** - Complete REST API via Django REST Framework
- ✅ **Testing** - Comprehensive test suite
- ✅ **Documentation** - Thorough documentation for developers
- ✅ **Logging & Error Handling** - Sophisticated error handling
- ✅ **Admin Interface** - Feature-rich admin panel

## Quick Start

### 1. Install the package

```bash
pip install django-reusable-comments
```

### 2. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    # ...
    'django_comments',
    # ...
]
```

### 3. Configure your settings

```python
DJANGO_COMMENTS_CONFIG = {
    'commentable_models': ['blog.Post', 'products.Product'],  # Models that can receive comments
    'use_uuids': False,  # Use integer PKs (set to True for UUID)
    'moderator_required': False,  # Set to True to enable moderation workflow
}
```

### 4. Run migrations

```bash
python manage.py migrate django_comments
```

### 5. Include URL patterns

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    # ...
    path('api/comments/', include('django_comments.api.urls')),
    # ...
]
```

## Documentation

For detailed documentation, visit [https://django-reusable-comments.readthedocs.io/](https://django-reusable-comments.readthedocs.io/)

## Example Usage

### Creating a comment via the API

```python
# Example POST to /api/comments/
{
    "content_type": "blog.post",  
    "object_id": "123",
    "user": 1,  # Optional, authenticated user ID or can be anonymous
    "content": "This is a great post!",
    "parent": null  # Optional, for threaded comments
}
```

### Using signals

```python
from django.dispatch import receiver
from django_comments.signals import comment_post_save

@receiver(comment_post_save)
def handle_new_comment(sender, comment, created, **kwargs):
    if created:
        # Do something with the new comment
        pass
```

## Contributing

Contributions are welcome! Please check out our [Contributing Guide](CONTRIBUTING.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.