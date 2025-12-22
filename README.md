# Django Reusable Comments

A **production-grade**, feature-complete Django app for adding sophisticated comment functionality to any model. Built with performance optimization, extensive customization options, email notifications, content formatting, spam detection, GDPR compliance, and full REST API support.

[![Python](https://img.shields.io/badge/python-3.8--3.12-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-3.2--5.0-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-280%2B%20passing-brightgreen.svg)]()

## ⚡ What's New in v1.0

- 📧 **8 Email Notification Types** - Beautiful HTML templates with async Celery support
- 🎨 **Content Formatting** - Plain text, Markdown, and HTML with XSS protection
- 🛡️ **Advanced Spam Detection** - ML-ready with custom detector callbacks
- ⏱️ **3-Tier Rate Limiting** - DRF integration with user/anon/burst protection
- 📄 **Smart Pagination** - Thread-aware pagination for nested comments
- 🔒 **Enhanced Security** - XSS protection, HTML sanitization, profanity filtering
- 🤖 **Auto-Moderation** - Threshold-based auto-hide, auto-delete, auto-ban
- 🚫 **Ban System** - Auto-ban after spam flags or rejections, temporary/permanent bans
- ✏️ **Comment Editing** - Time-windowed editing with full revision history
- ⚖️ **GDPR Compliance** - Data export, deletion, anonymization, retention policies
- ⚙️ **60+ Settings** - Complete configurability for every aspect

---

## 🚀 Features

### Core Features
- ✅ **Model Agnostic** - Add comments to any Django model
- ✅ **ID Flexibility** - Support for both UUID and integer primary keys
- ✅ **Threaded Comments** - Nested replies with configurable depth limits
- ✅ **Performance Optimized** - Advanced caching, query optimization, select_related
- ✅ **REST API** - Complete DRF integration with filtering, search, ordering
- ✅ **Admin Interface** - Feature-rich admin with bulk actions and optimized queries

### Content & Formatting
- 🎨 **Multiple Formats**
  - Plain text (HTML escaped - safest)
  - Markdown (with CommonMark extensions)
  - HTML (sanitized with bleach)
- 🔒 **XSS Protection** - Automatic HTML sanitization
- 📝 **Profanity Filtering** - Censor, flag, hide, or delete
- ✏️ **Comment Editing** - Configurable time windows
- 📜 **Edit History** - Complete revision tracking

### Spam & Content Control
- 🛡️ **Spam Detection**
  - Word-based detection
  - Custom ML detector callbacks
  - Configurable actions (flag/hide/delete)
- 🚨 **Auto-Moderation**
  - Auto-hide after N flags
  - Auto-delete after N flags
  - Auto-ban spammers
- 🚫 **Flag System**
  - Spam, inappropriate, harassment flags
  - Abuse prevention (rate limits)
  - Moderator notifications

### Moderation & Workflows
- 👮 **Moderation Queue**
  - Approve/reject workflow
  - Group-based permissions
  - Auto-approval for trusted users
- 🔨 **Ban System**
  - Auto-ban after rejections/spam flags
  - Temporary or permanent bans
  - Ban notifications
- 📊 **Moderation Logs**
  - Complete audit trail
  - 90-day default retention
  - All actions logged

### Notifications
- 📧 **8 Notification Types**
  1. New comment notifications
  2. Reply notifications
  3. Approval notifications
  4. Rejection notifications
  5. Moderator alerts (non-public comments)
  6. User ban notifications
  7. User unban notifications
  8. Flag threshold notifications

- ⚡ **Async Support**
  - Celery integration (optional)
  - Graceful fallback to sync
  - Beautiful HTML email templates

### API Features
- ⏱️ **Rate Limiting**
  - User limits (default: 100/day)
  - Anonymous limits (default: 20/day)
  - Burst protection (default: 5/min)
  - DRF throttling integration

- 📄 **Pagination**
  - Standard pagination
  - Thread-aware pagination
  - Configurable page sizes
  - Client-controlled page size

- 🔍 **Advanced Filtering**
  - Filter by user, content object, public status
  - Full-text search
  - Date range filtering
  - Custom ordering

### GDPR Compliance
- ⚖️ **Data Subject Rights**
  - Right to data portability (export)
  - Right to erasure (deletion)
  - Right to be forgotten (anonymization)
  
- 🔐 **Privacy Controls**
  - Optional IP address collection
  - Optional user agent collection
  - Auto-anonymize on user deletion
  - Retention policy automation

- 📋 **Data Management**
  - Export all user data as JSON
  - Anonymize old comments automatically
  - Management commands for compliance

### Developer Experience
- ✅ **Signals** - Robust signal system for extending functionality
- 🌍 **Internationalization** - Full i18n support using gettext_lazy
- 🏷️ **Template Tags** - Convenient template tags with caching
- 🧪 **Testing** - Comprehensive test suite (280+ tests)
- 📚 **Documentation** - Thorough documentation for developers
- 🪵 **Logging** - Sophisticated error handling and logging

---

## 📦 Installation

### Quick Install

```bash
# Install the package
pip install django-reusable-comments

# Install optional dependencies
pip install markdown bleach  # For formatting support
pip install celery  # For async notifications (optional)
```

### Add to INSTALLED_APPS

```python
# settings.py

INSTALLED_APPS = [
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required for email notifications
    
    # Third-party apps
    'rest_framework',
    'django_filters',
    
    # Django comments
    'django_comments',
    
    # Your apps
    # ...
]

SITE_ID = 1  # Required for email notifications
```

### Run Migrations

```bash
python manage.py migrate django_comments
```

### Include URL Patterns

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/comments/', include('django_comments.urls')),
    # Your URLs
]
```

---

## ⚙️ Configuration

### Minimal Configuration

```python
# settings.py

DJANGO_COMMENTS_CONFIG = {
    # Required: Specify which models can receive comments
    'COMMENTABLE_MODELS': [
        'blog.Post',
        'products.Product',
    ],
}
```

### Basic Configuration

```python
# settings.py

DJANGO_COMMENTS_CONFIG = {
    # Models that can receive comments
    'COMMENTABLE_MODELS': ['blog.Post', 'products.Product'],
    
    # Enable features
    'SEND_NOTIFICATIONS': True,
    'COMMENT_FORMAT': 'markdown',  # 'plain', 'markdown', or 'html'
    'ALLOW_ANONYMOUS': False,
    
    # Moderation
    'MODERATOR_REQUIRED': True,
    'AUTO_APPROVE_GROUPS': ['Moderators', 'Staff'],
    'AUTO_APPROVE_AFTER_N_APPROVED': 5,
    
    # Threading
    'MAX_COMMENT_DEPTH': 3,
    
    # API Rate Limiting
    'API_RATE_LIMIT': '100/day',
    'API_RATE_LIMIT_ANON': '20/day',
    'API_RATE_LIMIT_BURST': '5/min',
}
```

### Production Configuration

```python
# settings.py

DJANGO_COMMENTS_CONFIG = {
    # Models
    'COMMENTABLE_MODELS': ['blog.Post', 'products.Product', 'news.Article'],
    
    # Content
    'MAX_COMMENT_LENGTH': 3000,
    'ALLOW_ANONYMOUS': False,
    'COMMENT_FORMAT': 'markdown',
    'MAX_COMMENT_DEPTH': 3,
    
    # Moderation
    'MODERATOR_REQUIRED': True,
    'AUTO_APPROVE_GROUPS': ['Moderators', 'Staff'],
    'AUTO_APPROVE_AFTER_N_APPROVED': 5,
    'TRUSTED_USER_GROUPS': ['Premium', 'Verified'],
    
    # Spam Detection
    'SPAM_DETECTION_ENABLED': True,
    'SPAM_DETECTOR': 'myapp.ml.detect_spam',  # Custom ML detector
    'SPAM_ACTION': 'flag',
    
    # Profanity Filtering
    'PROFANITY_FILTERING': True,
    'PROFANITY_LIST': ['badword1', 'badword2'],
    'PROFANITY_ACTION': 'censor',
    
    # Auto-Moderation
    'AUTO_HIDE_THRESHOLD': 3,
    'AUTO_DELETE_THRESHOLD': 10,
    'FLAG_NOTIFICATION_THRESHOLD': 1,
    'AUTO_HIDE_DETECTED_SPAM': True,
    
    # Ban System
    'AUTO_BAN_AFTER_REJECTIONS': 5,
    'AUTO_BAN_AFTER_SPAM_FLAGS': 3,
    'DEFAULT_BAN_DURATION_DAYS': 30,
    
    # Notifications
    'SEND_NOTIFICATIONS': True,
    'USE_ASYNC_NOTIFICATIONS': True,  # Requires Celery
    'NOTIFY_ON_FLAG': True,
    'NOTIFY_ON_AUTO_HIDE': True,
    
    # API
    'API_RATE_LIMIT': '100/day',
    'API_RATE_LIMIT_ANON': '20/day',
    'API_RATE_LIMIT_BURST': '5/min',
    'PAGE_SIZE': 20,
    'MAX_PAGE_SIZE': 100,
    
    # Editing
    'ALLOW_COMMENT_EDITING': True,
    'EDIT_TIME_WINDOW': 3600,  # 1 hour
    'TRACK_EDIT_HISTORY': True,
    
    # GDPR
    'GDPR_ENABLED': True,
    'GDPR_ALLOW_USER_DATA_EXPORT': True,
    'GDPR_ALLOW_USER_DATA_DELETION': True,
    'GDPR_ANONYMIZE_ON_USER_DELETE': True,
    'GDPR_ENABLE_RETENTION_POLICY': True,
    'GDPR_RETENTION_DAYS': 365,
    
    # Caching
    'CACHE_TIMEOUT': 3600,
    
    # Logging
    'LOGGER_NAME': 'django_comments',
}
```

For complete configuration reference, see [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md).

---

## 📧 Email Notifications

### Setup

```python
# settings.py

DJANGO_COMMENTS_CONFIG = {
    'SEND_NOTIFICATIONS': True,
    'DEFAULT_FROM_EMAIL': 'noreply@yourdomain.com',
    'COMMENT_NOTIFICATION_EMAILS': ['moderators@yourdomain.com'],
}

# Configure Django email backend
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-password'
```

### Async Notifications with Celery

```python
# settings.py

DJANGO_COMMENTS_CONFIG = {
    'SEND_NOTIFICATIONS': True,
    'USE_ASYNC_NOTIFICATIONS': True,
}

# Celery configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
```

### Custom Email Templates

```python
DJANGO_COMMENTS_CONFIG = {
    'NOTIFICATION_EMAIL_TEMPLATE': 'myapp/emails/new_comment.html',
    'NOTIFICATION_REPLY_TEMPLATE': 'myapp/emails/comment_reply.html',
    'NOTIFICATION_APPROVED_TEMPLATE': 'myapp/emails/approved.html',
    'NOTIFICATION_REJECTED_TEMPLATE': 'myapp/emails/rejected.html',
    'NOTIFICATION_MODERATOR_TEMPLATE': 'myapp/emails/moderator_alert.html',
    'NOTIFICATION_USER_BAN_TEMPLATE': 'myapp/emails/banned.html',
    'NOTIFICATION_USER_UNBAN_TEMPLATE': 'myapp/emails/unbanned.html',
    'NOTIFICATION_FLAG_TEMPLATE': 'myapp/emails/flag_alert.html',
}
```

---

## 🤖 Custom Spam Detection

### Simple Word-Based Detection

```python
DJANGO_COMMENTS_CONFIG = {
    'SPAM_DETECTION_ENABLED': True,
    'SPAM_WORDS': [
        'viagra', 'casino', 'lottery', 'prize', 
        'click here', 'buy now', 'limited time'
    ],
    'SPAM_ACTION': 'flag',
}
```

### Custom ML-Based Detection

```python
# myapp/spam.py
import joblib

# Load your trained model
model = joblib.load('path/to/spam_model.pkl')
vectorizer = joblib.load('path/to/vectorizer.pkl')

def detect_spam(content):
    """
    Custom spam detection using ML model.
    
    Args:
        content (str): Comment content to check
        
    Returns:
        tuple: (is_spam: bool, reason: str)
    """
    # Vectorize and predict
    features = vectorizer.transform([content])
    prediction = model.predict(features)[0]
    probability = model.predict_proba(features)[0][1]
    
    if prediction == 1:  # Spam
        return True, f"Spam detected (confidence: {probability:.2%})"
    
    return False, None

# settings.py
DJANGO_COMMENTS_CONFIG = {
    'SPAM_DETECTION_ENABLED': True,
    'SPAM_DETECTOR': 'myapp.spam.detect_spam',
    'SPAM_ACTION': 'hide',  # Auto-hide detected spam
}
```

---

## 🚫 Auto-Moderation System

### Flag-Based Auto-Moderation

```python
DJANGO_COMMENTS_CONFIG = {
    # Hide comment after 3 user flags
    'AUTO_HIDE_THRESHOLD': 3,
    
    # Delete comment after 10 user flags
    'AUTO_DELETE_THRESHOLD': 10,
    
    # Notify moderators at first flag
    'FLAG_NOTIFICATION_THRESHOLD': 1,
    
    # Auto-hide detected spam immediately
    'AUTO_HIDE_DETECTED_SPAM': True,
}
```

### Auto-Ban System

```python
DJANGO_COMMENTS_CONFIG = {
    # Ban user after 5 rejected comments
    'AUTO_BAN_AFTER_REJECTIONS': 5,
    
    # Ban user after 3 spam flags across all their comments
    'AUTO_BAN_AFTER_SPAM_FLAGS': 3,
    
    # Default ban duration (None = permanent)
    'DEFAULT_BAN_DURATION_DAYS': 30,
}
```

**How Auto-Ban Works:**
1. User posts spammy content
2. Comments get flagged or rejected
3. When thresholds reached → User automatically banned
4. Ban notification sent to user
5. All future comment attempts blocked

---

## ✏️ Comment Editing

### Enable Editing

```python
DJANGO_COMMENTS_CONFIG = {
    # Allow users to edit their comments
    'ALLOW_COMMENT_EDITING': True,
    
    # 1 hour editing window
    'EDIT_TIME_WINDOW': 3600,
    
    # Track all edits
    'TRACK_EDIT_HISTORY': True,
}
```

### API Usage

```python
# Edit a comment
PATCH /api/comments/{id}/
{
    "content": "Updated comment content"
}

# View edit history (admin only)
GET /api/comments/{id}/revisions/
```

---

## ⚖️ GDPR Compliance

### Enable GDPR Features

```python
DJANGO_COMMENTS_CONFIG = {
    'GDPR_ENABLED': True,
    
    # User rights
    'GDPR_ALLOW_USER_DATA_EXPORT': True,
    'GDPR_ALLOW_USER_DATA_DELETION': True,
    
    # Auto-anonymize when user account deleted
    'GDPR_ANONYMIZE_ON_USER_DELETE': True,
    
    # Retention policy
    'GDPR_ENABLE_RETENTION_POLICY': True,
    'GDPR_RETENTION_DAYS': 365,
    
    # Privacy settings
    'GDPR_COLLECT_IP_ADDRESS': True,
    'GDPR_COLLECT_USER_AGENT': True,
    'GDPR_ANONYMIZE_IP_ON_RETENTION': True,
}
```

### Data Export

```python
from django_comments.gdpr import export_user_data

# Export all user's comment data
data = export_user_data(user)
# Returns: {
#     'comments': [...],
#     'flags': [...],
#     'moderation_actions': [...],
#     'export_date': '2025-01-15T10:30:00Z'
# }
```

### Data Deletion/Anonymization

```python
from django_comments.gdpr import anonymize_user_data

# Anonymize all user's data
anonymize_user_data(user)
# Anonymizes: username, email, IP addresses, user agent
# Keeps: comment content (attributed to "Anonymous")
```

### Management Commands

```bash
# Anonymize comments older than retention period
python manage.py anonymize_old_comments

# Schedule in cron
0 2 * * 0 python manage.py anonymize_old_comments  # Weekly at 2 AM
```

---

## 🔌 API Endpoints

### Comments

```http
# List comments
GET /api/comments/
GET /api/comments/?content_type=blog.post&object_id=123
GET /api/comments/?user=5&is_public=true
GET /api/comments/?search=keyword
GET /api/comments/?ordering=-created_at

# Create comment
POST /api/comments/
{
    "content_type": "blog.post",
    "object_id": "123",
    "content": "Great article!",
    "parent": null
}

# Get comment
GET /api/comments/{id}/

# Update comment
PATCH /api/comments/{id}/
{
    "content": "Updated content"
}

# Delete comment
DELETE /api/comments/{id}/

# Approve comment (moderators only)
POST /api/comments/{id}/approve/

# Reject comment (moderators only)
POST /api/comments/{id}/reject/

# Flag comment
POST /api/comments/{id}/flag/
{
    "flag": "spam",  # or "inappropriate", "harassment"
    "reason": "This is spam"
}
```

### Flags

```http
# List flags (moderators only)
GET /api/flags/
GET /api/flags/?comment={comment_id}
GET /api/flags/?user={user_id}
GET /api/flags/?flag=spam

# Review flag (moderators only)
POST /api/flags/{id}/review/
{
    "action": "approve"  # or "dismiss"
}
```

### Banned Users

```http
# List banned users (moderators only)
GET /api/banned-users/
GET /api/banned-users/?is_active=true

# Ban user (moderators only)
POST /api/banned-users/
{
    "user": 5,
    "reason": "Repeated spam",
    "banned_until": "2025-02-15T00:00:00Z"  # null for permanent
}

# Unban user (moderators only)
DELETE /api/banned-users/{id}/
```

### Content Object Comments

```http
# Get all comments for a specific object
GET /api/content-comments/
?content_type=blog.post
&object_id=123
&ordering=-created_at
```

---

## 🏷️ Template Tags

### Load Template Tags

```django
{% load comment_tags %}
```

### Display Comments

```django
{# Render comment form #}
{% render_comment_form for article %}

{# Display comment count #}
{% get_comment_count for article as comment_count %}
<p>{{ comment_count }} comments</p>

{# List comments #}
{% get_comments for article as comments %}
{% for comment in comments %}
    <div class="comment">
        <strong>{{ comment.user.username }}</strong>
        <p>{{ comment.content }}</p>
        <small>{{ comment.created_at }}</small>
    </div>
{% endfor %}

{# Check if user can comment #}
{% can_comment user article as can_post %}
{% if can_post %}
    <a href="{% url 'add_comment' %}">Add Comment</a>
{% endif %}
```

---

## 🔔 Signals

### Available Signals

```python
from django_comments.signals import (
    comment_created,
    comment_updated,
    comment_deleted,
    comment_flagged,
    comment_approved,
    comment_rejected,
    user_banned,
    user_unbanned,
)
```

### Example Usage

```python
from django.dispatch import receiver
from django_comments.signals import comment_created, comment_flagged

@receiver(comment_created)
def notify_on_new_comment(sender, instance, **kwargs):
    """Send custom notification when comment is created."""
    print(f"New comment: {instance.content}")
    # Your custom logic here

@receiver(comment_flagged)
def handle_flagged_comment(sender, instance, flag, user, **kwargs):
    """Handle when comment is flagged."""
    if flag == 'spam':
        # Custom spam handling
        pass
```

---

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
python manage.py test django_comments

# Run specific test modules
python manage.py test django_comments.tests.test_models
python manage.py test django_comments.tests.test_views
python manage.py test django_comments.tests.test_signals

# Run with coverage
pip install coverage
coverage run --source='django_comments' manage.py test django_comments
coverage report
```

**Test Coverage:**
- 280+ tests
- 95%+ code coverage
- All critical paths tested
- Edge cases covered

---

## 📋 Management Commands

### Cleanup Comments

```bash
# Remove non-public comments older than CLEANUP_AFTER_DAYS
python manage.py cleanup_comments

# Dry run (show what would be deleted)
python manage.py cleanup_comments --dry-run
```

### Anonymize Old Comments (GDPR)

```bash
# Anonymize personal data older than GDPR_RETENTION_DAYS
python manage.py anonymize_old_comments

# Dry run
python manage.py anonymize_old_comments --dry-run
```

### Moderation Queue

```bash
# Show comments pending moderation
python manage.py show_moderation_queue

# Show specific status
python manage.py show_moderation_queue --status=flagged
```

---

## 🎯 Use Cases

### Blog Comments

```python
# models.py
from django.db import models

class Post(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    published = models.DateTimeField(auto_now_add=True)

# settings.py
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['blog.Post'],
    'COMMENT_FORMAT': 'markdown',
    'ALLOW_ANONYMOUS': True,
    'MODERATOR_REQUIRED': False,
}
```

### Product Reviews

```python
# models.py
class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)

# settings.py
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['products.Product'],
    'MODERATOR_REQUIRED': True,  # Review all product feedback
    'ALLOW_ANONYMOUS': False,  # Verified purchases only
    'SEND_NOTIFICATIONS': True,
}
```

### Community Forum

```python
# settings.py
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['forum.Thread'],
    'MAX_COMMENT_DEPTH': None,  # Unlimited threading
    'ALLOW_COMMENT_EDITING': True,
    'EDIT_TIME_WINDOW': None,  # Edit anytime
    'TRACK_EDIT_HISTORY': True,
    'SPAM_DETECTION_ENABLED': True,
    'AUTO_BAN_AFTER_SPAM_FLAGS': 3,
}
```

---

## 🔐 Security Considerations

### XSS Protection

```python
# HTML format with sanitization
DJANGO_COMMENTS_CONFIG = {
    'COMMENT_FORMAT': 'html',
}

# Only these tags allowed by default:
# <p>, <br>, <strong>, <em>, <a>, <code>, <pre>, <ul>, <ol>, <li>
```

### Rate Limiting

```python
# Prevent spam/abuse
DJANGO_COMMENTS_CONFIG = {
    'API_RATE_LIMIT': '100/day',
    'API_RATE_LIMIT_ANON': '20/day',
    'API_RATE_LIMIT_BURST': '5/min',
    'MAX_FLAGS_PER_DAY': 20,
    'MAX_FLAGS_PER_HOUR': 5,
}
```

### Content Validation

```python
# Automatic content checking
DJANGO_COMMENTS_CONFIG = {
    'SPAM_DETECTION_ENABLED': True,
    'PROFANITY_FILTERING': True,
    'MAX_COMMENT_LENGTH': 3000,
}
```

---

## 🚀 Performance Tips

### Caching

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}

DJANGO_COMMENTS_CONFIG = {
    'CACHE_TIMEOUT': 3600,  # 1 hour
}
```

### Database Optimization

```python
# Use select_related and prefetch_related in queries
from django_comments.models import Comment

# Efficient querying
comments = Comment.objects.select_related('user', 'content_type').filter(
    is_public=True
)
```

### Async Notifications

```python
# Use Celery for async email sending
DJANGO_COMMENTS_CONFIG = {
    'USE_ASYNC_NOTIFICATIONS': True,
}
```

---

## 🤝 Contributing

We love contributions! Here's how to get started:

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Make your changes**
4. **Run tests**
   ```bash
   python manage.py test django_comments
   ```
5. **Commit your changes**
   ```bash
   git commit -m "Add amazing feature"
   ```
6. **Push to your fork**
   ```bash
   git push origin feature/amazing-feature
   ```
7. **Open a Pull Request**

Please check out our [Contributing Guide](CONTRIBUTING.md) for more details.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/NzeStan/django-reusable-comments.git
cd django-reusable-comments

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Or install using requirements files
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
python manage.py test django_comments
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support

- **Documentation**: [Full Documentation](https://django-reusable-comments.readthedocs.io/)
- **Issues**: [GitHub Issues](https://github.com/NzeStan/django-reusable-comments/issues)
- **Discussions**: [GitHub Discussions](https://github.com/NzeStan/django-reusable-comments/discussions)

---

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

---

## 🏆 Credits

**Developed and maintained by Ifeanyi Stanley Nnamani**

Special thanks to all contributors who have helped improve this package!

---

## 🌟 Star History

If you find this package useful, please consider giving it a ⭐ on GitHub!

---

## 📊 Quick Stats

- **280+ Tests** - Comprehensive test coverage
- **60+ Settings** - Complete configurability
- **8 Notification Types** - Full email system
- **GDPR Compliant** - Privacy-first design
- **Production Ready** - Battle-tested code

---

**Ready to add comments to your Django project?** Install now and get started in 15 minutes! 🚀

```bash
pip install django-reusable-comments
```