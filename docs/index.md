# Django Reusable Comments

**Production-grade Django comments system with REST API, moderation, spam detection, and GDPR compliance.**

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-3.2+-green.svg)](https://www.djangoproject.com/)
[![Django REST Framework](https://img.shields.io/badge/DRF-3.14.0+-orange.svg)](https://www.django-rest-framework.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/NzeStan/django-reusable-comments/blob/main/LICENSE)
[![Tests](https://img.shields.io/badge/tests-280%2B%20passing-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)]()

---

## Overview

`django-reusable-comments` is a sophisticated, production-ready Django package that provides a comprehensive commenting system for your Django applications. Built with performance, security, and flexibility in mind, it offers extensive features while remaining easy to integrate and customize.

### Key Highlights

- ✅ **Production-Ready** - Battle-tested with 280+ comprehensive tests
- 🚀 **High Performance** - Optimized queries, caching, and async support
- 🔒 **Security First** - XSS protection, rate limiting, spam detection
- ⚖️ **GDPR Compliant** - Data export, deletion, and anonymization
- 📧 **Rich Notifications** - 8 email types with beautiful HTML templates
- 🎨 **Flexible Formatting** - Plain text, Markdown, and sanitized HTML
- 🛡️ **Advanced Moderation** - Auto-hide, auto-delete, auto-ban
- 🔌 **REST API** - Complete DRF integration with filtering and pagination

---

## What's New in v1.0

### Email Notifications 📧
- 8 notification types (new comment, reply, approval, rejection, ban, etc.)
- Beautiful HTML email templates
- Async support via built-in threading (no broker required)
- Per-notification-type configuration

### Content & Security 🎨
- Multiple format support: Plain text, Markdown, HTML
- XSS protection with bleach sanitization
- Profanity filtering with configurable actions
- ML-ready spam detection with custom callbacks

### Advanced Moderation 🛡️
- Threshold-based auto-hide and auto-delete
- Auto-ban system (after spam flags or rejections)
- Temporary and permanent bans
- Complete moderation logs with 90-day retention

### API Features 🔌
- 3-tier rate limiting (user/anonymous/burst)
- Thread-aware pagination
- Advanced filtering and search
- Bulk moderation actions

### GDPR Compliance ⚖️
- Data export (Article 20)
- Data deletion (Article 17)
- Auto-anonymization on user deletion
- Retention policy automation
- Privacy-first data collection controls

### Developer Experience 🔧
- 60+ configuration settings
- Comprehensive signal system
- Template tags with caching
- Management commands
- Full i18n support

---

## Quick Start

### 1. Install

```bash
pip install django-reusable-comments
```

### 2. Configure

```python
# settings.py

INSTALLED_APPS = [
    # ...
    'rest_framework',
    'django_filters',
    'django_comments',
]

DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['blog.Post'],
    'MODERATOR_REQUIRED': False,
    'MAX_COMMENT_DEPTH': 3,
}
```

### 3. Setup URLs

```python
# urls.py

urlpatterns = [
    path('api/comments/', include('django_comments.api.urls')),
]
```

### 4. Migrate

```bash
python manage.py migrate django_comments
```

**That's it!** Your comment system is ready. 🎉

---

## Feature Overview

### Core Features

#### Model Agnostic
Comment on any Django model using ContentType framework:
```python
'COMMENTABLE_MODELS': [
    'blog.Post',
    'products.Product',
    'news.Article',
]
```

#### Flexible ID Support
Works with both UUID and integer primary keys:
```python
Comment.objects.create(
    content_type='blog.post',
    object_id='123',  # Integer or UUID
    content='Great article!'
)
```

#### Threaded Comments
Nested replies with configurable depth limits:
```python
'MAX_COMMENT_DEPTH': 3,  # None for unlimited
```

### Content & Formatting

#### Multiple Formats
```python
'COMMENT_FORMAT': 'plain',    # HTML escaped (safest)
'COMMENT_FORMAT': 'markdown', # CommonMark with extensions
'COMMENT_FORMAT': 'html',     # Sanitized with bleach
```

#### XSS Protection
Automatic HTML sanitization:
```python
from django_comments.formatting import render_comment_content

safe_html = render_comment_content(comment, format_type='html')
```

#### Profanity Filtering
```python
'PROFANITY_FILTERING': True,
'PROFANITY_LIST': ['badword1', 'badword2'],
'PROFANITY_ACTION': 'censor',  # 'censor', 'flag', 'hide', 'delete'
```

### Spam & Moderation

#### Spam Detection
Built-in word-based detection plus custom ML callbacks:
```python
'SPAM_DETECTION_ENABLED': True,
'SPAM_DETECTOR': 'myapp.ml.detect_spam',
'SPAM_ACTION': 'flag',  # 'flag', 'hide', 'delete'
```

#### Auto-Moderation
Threshold-based automatic actions:
```python
'AUTO_HIDE_THRESHOLD': 3,      # Hide after 3 flags
'AUTO_DELETE_THRESHOLD': 10,   # Delete after 10 flags
'AUTO_HIDE_DETECTED_SPAM': True,
```

#### Auto-Ban System
```python
'AUTO_BAN_AFTER_REJECTIONS': 5,
'AUTO_BAN_AFTER_SPAM_FLAGS': 3,
'DEFAULT_BAN_DURATION_DAYS': 30,  # None = permanent
```

### API Features

#### Rate Limiting
3-tier protection:
```python
'API_RATE_LIMIT': '100/day',        # Authenticated users
'API_RATE_LIMIT_ANON': '20/day',    # Anonymous users
'API_RATE_LIMIT_BURST': '5/min',    # Burst protection
```

#### Advanced Filtering
```bash
GET /api/comments/?content_type=blog.post&object_id=123
GET /api/comments/?user=5&is_public=true
GET /api/comments/?search=keyword
GET /api/comments/?ordering=-created_at
```

#### Bulk Actions
```python
POST /api/comments/bulk_approve/
{
    "comment_ids": ["uuid1", "uuid2", "uuid3"]
}
```

### Notifications

#### 8 Notification Types
1. New comment notifications
2. Reply notifications
3. Approval notifications
4. Rejection notifications
5. Moderator alerts (non-public comments)
6. User ban notifications
7. User unban notifications
8. Flag threshold notifications

#### Async Support
```python
'USE_ASYNC_NOTIFICATIONS': True,  # Uses built-in threading (no broker needed)
```

### GDPR Compliance

#### Data Subject Rights
```python
from django_comments.gdpr import export_user_data, anonymize_user_data

# Export all user data (Article 20)
data = export_user_data(user)

# Anonymize user data (Article 17)
anonymize_user_data(user)
```

#### Retention Policy
```python
'GDPR_ENABLE_RETENTION_POLICY': True,
'GDPR_RETENTION_DAYS': 365,
'GDPR_ANONYMIZE_IP_ON_RETENTION': True,
```

---

## Documentation

### Getting Started
- **[Installation Guide](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/installation.md)** - Step-by-step installation and setup
- **[Configuration Guide](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/configuration.md)** - Complete settings reference (60+ settings)
- **[Quick Start Examples](#quick-start)** - Get up and running in minutes

### Core Documentation
- **[API Reference](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/api_reference.md)** - Complete REST API documentation
- **[Advanced Usage](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/advanced_usage.md)** - Advanced features and patterns
- **[Contributing](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/contributing.md)** - Contribution guidelines

### Feature Guides
- **Moderation** - Approval workflows, auto-moderation, ban system
- **Spam Detection** - Word-based and ML-based spam filtering
- **Email Notifications** - Setup, templates, async with threading
- **GDPR Compliance** - Data export, deletion, anonymization
- **Template Tags** - Django template integration
- **Signals** - Extending functionality with signals

---

## Architecture

### Database Schema

```
┌─────────────────────┐
│ Comment             │
├─────────────────────┤
│ id (UUID/PK)        │
│ content_type_id     │
│ object_id           │
│ user_id             │
│ parent_id (FK)      │─┐
│ thread_id           │ │
│ depth               │ │
│ content             │ │ Self-referential
│ is_public           │ │ for threading
│ is_removed          │ │
│ created_at          │ │
│ updated_at          │◄┘
└─────────────────────┘
         │
         ├─► CommentFlag (spam, inappropriate, harassment)
         ├─► CommentRevision (edit history)
         ├─► ModerationAction (approval/rejection logs)
         └─► BannedUser (user bans)
```

### Key Components

**Models**
- `Comment` - Main comment model with threading
- `CommentFlag` - User-reported flags
- `BannedUser` - User ban records
- `CommentRevision` - Edit history
- `ModerationAction` - Moderation logs

**API Views**
- `CommentViewSet` - CRUD + bulk actions
- `FlagViewSet` - Flag management
- `BannedUserViewSet` - Ban management
- `ContentObjectCommentsViewSet` - Object-specific comments

**Utilities**
- `formatting.py` - Content formatting and sanitization
- `spam.py` - Spam detection
- `profanity.py` - Profanity filtering
- `gdpr.py` - GDPR compliance utilities
- `notifications.py` - Email notifications

**Admin**
- Comprehensive admin interface
- Bulk moderation actions
- Advanced filtering
- Optimized queries

---

## Use Cases

### Blog Comments
```python
# models.py
class Post(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()

# settings.py
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['blog.Post'],
    'MODERATOR_REQUIRED': False,
    'ALLOW_ANONYMOUS': False,
}
```

### Product Reviews
```python
# settings.py
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['products.Product'],
    'MODERATOR_REQUIRED': True,  # Review all submissions
    'SPAM_DETECTION_ENABLED': True,
    'PROFANITY_FILTERING': True,
}
```

### News Site with Heavy Moderation
```python
# settings.py
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['news.Article'],
    'MODERATOR_REQUIRED': True,
    'AUTO_APPROVE_GROUPS': ['Verified Users'],
    'AUTO_HIDE_THRESHOLD': 2,
    'AUTO_BAN_AFTER_SPAM_FLAGS': 3,
    'GDPR_ENABLED': True,
}
```

### Forum-Style Threading
```python
# settings.py
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['forum.Thread'],
    'MAX_COMMENT_DEPTH': 5,  # Deep threading
    'ALLOW_COMMENT_EDITING': True,
    'EDIT_TIME_WINDOW': 3600,  # 1 hour
}
```

---

## Performance

### Query Optimization
- `select_related()` for foreign keys
- `prefetch_related()` for reverse relations
- Database indexes on frequently queried fields
- Efficient pagination with keyset pagination option

### Caching
```python
'CACHE_TIMEOUT': 3600,  # 1 hour cache for counts

from django.core.cache import cache
cache_key = f'comment_count_{obj_id}'
```

### Async Operations
```python
# Async notifications use built-in threading — enable in settings:
DJANGO_COMMENTS_CONFIG = {
    'SEND_NOTIFICATIONS': True,
    'USE_ASYNC_NOTIFICATIONS': True,  # dispatches in a daemon Thread
}
```

### Database Considerations
- Use UUIDs for better distributed systems support
- PostgreSQL recommended for production
- Regular database maintenance (VACUUM, ANALYZE)

---

## Security

### XSS Protection
- All user content HTML-escaped by default
- HTML sanitization with bleach for HTML format
- Safe rendering in templates

### SQL Injection Prevention
- Django ORM protects against SQL injection
- Parameterized queries throughout
- Proper validation of all inputs

### Rate Limiting
- 3-tier rate limiting (user/anonymous/burst)
- DRF throttling integration
- Per-endpoint rate limits

### CSRF Protection
- Django CSRF middleware required
- CSRF tokens in all forms
- API authentication required for write operations

### Permission System
- Django permissions integration
- Group-based auto-approval
- Moderator-only actions protected

---

## Testing

### Test Suite
- **280+ tests** covering all functionality
- **90% code coverage** with branch coverage
- Integration, unit, and API tests
- Performance benchmarks

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=django_comments --cov-report=html

# Run specific test module
pytest django_comments/tests/test_views.py

# Run parallel tests
pytest -n auto
```

### Test Categories
```python
@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.api
@pytest.mark.models
@pytest.mark.permissions
@pytest.mark.signals
@pytest.mark.admin
@pytest.mark.security
```

---

## Community & Support

### Getting Help
- **Documentation**: [https://django-reusable-comments.readthedocs.io/](https://django-reusable-comments.readthedocs.io/)
- **GitHub Issues**: [Report bugs or request features](https://github.com/NzeStan/django-reusable-comments/issues)
- **Discussions**: [Ask questions and share ideas](https://github.com/NzeStan/django-reusable-comments/discussions)

### Contributing
We welcome contributions! See [Contributing Guide](contributing.md) for:
- How to set up development environment
- Code style guidelines
- Testing requirements
- Pull request process

### License
MIT License - see [LICENSE](https://github.com/NzeStan/django-reusable-comments/blob/main/LICENSE) file

---

## Roadmap

### v1.1 (Planned)
- [ ] GraphQL API support
- [ ] Real-time notifications with WebSockets
- [ ] Advanced analytics and reporting
- [ ] Comment reactions (likes, upvotes)
- [ ] Media attachments (images, files)

### v1.2 (Planned)
- [ ] Multi-language comment moderation
- [ ] Advanced spam detection with AI
- [ ] Comment pinning and highlighting
- [ ] Comment import/export tools
- [ ] Enhanced admin dashboard

### Future Considerations
- Vue.js/React frontend components
- Comment voting system
- Badge system for users
- User reputation scoring
- Advanced analytics dashboard

---

## Credits

**Author**: Ifeanyi Stanley Nnamani  
**Email**: nnamaniifeanyi10@gmail.com  
**GitHub**: [@NzeStan](https://github.com/NzeStan)

### Built With
- [Django](https://www.djangoproject.com/) - Web framework
- [Django REST Framework](https://www.django-rest-framework.org/) - API framework
- [django-filter](https://django-filter.readthedocs.io/) - Filtering support
- [bleach](https://bleach.readthedocs.io/) - HTML sanitization
- [Python threading](https://docs.python.org/3/library/threading.html) - Built-in async task dispatch

---

## Acknowledgments

Special thanks to:
- Django and DRF communities for excellent frameworks
- All contributors and testers
- Users who provided feedback and feature requests

---

**Ready to add comments to your Django project?**  
Start with the [Installation Guide](installation.md) →