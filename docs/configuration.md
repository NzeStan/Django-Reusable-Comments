# Django Reusable Comments - Complete Configuration Guide

This guide documents all available settings for `django-reusable-comments` v1.0+.

## Table of Contents

- [Model Configuration](#model-configuration)
- [Moderation Settings](#moderation-settings)
- [Threading Settings](#threading-settings)
- [Content Settings](#content-settings)
- [Sorting & Display](#sorting--display)
- [API Pagination](#api-pagination)
- [API Rate Limiting](#api-rate-limiting)
- [Notifications](#notifications)
- [Cleanup Settings](#cleanup-settings)
- [Logging](#logging)
- [Spam Detection](#spam-detection)
- [Profanity Filtering](#profanity-filtering)
- [Caching](#caching)
- [Flag Thresholds & Auto-Moderation](#flag-thresholds--auto-moderation)
- [Trusted Users & Auto-Approval](#trusted-users--auto-approval)
- [Flag Abuse Prevention](#flag-abuse-prevention)
- [Enhanced Notifications](#enhanced-notifications)
- [Comment Editing](#comment-editing)
- [Moderation Queue](#moderation-queue)
- [Ban System](#ban-system)
- [GDPR Compliance](#gdpr-compliance)

---

## Model Configuration

```python
DJANGO_COMMENTS_CONFIG = {
    # List of models that can be commented on
    # Format: ['app_label.ModelName', 'another_app.AnotherModel']
    'COMMENTABLE_MODELS': [],
}
```

**Description:** Defines which models in your Django project can receive comments.

**Example:**
```python
'COMMENTABLE_MODELS': [
    'blog.Post',
    'products.Product',
    'news.Article',
],
```

---

## Moderation Settings

```python
DJANGO_COMMENTS_CONFIG = {
    # Whether moderation is required before comments are public
    # If True, all new comments will have is_public=False until approved
    'MODERATOR_REQUIRED': False,
    
    # Auto-approve comments by users belonging to these groups
    # Users in these groups bypass MODERATOR_REQUIRED
    'AUTO_APPROVE_GROUPS': ['Moderators', 'Staff'],
    
    # Who can see non-public comments
    # Users in these groups can view comments with is_public=False
    'CAN_VIEW_NON_PUBLIC_COMMENTS': ['Moderators', 'Staff'],
}
```

**Key Points:**
- `MODERATOR_REQUIRED`: When `True`, all comments wait for moderator approval
- `AUTO_APPROVE_GROUPS`: Users in these groups bypass moderation
- `CAN_VIEW_NON_PUBLIC_COMMENTS`: Controls who can see pending/rejected comments

---

## Threading Settings

```python
DJANGO_COMMENTS_CONFIG = {
    # Maximum comment depth for threaded comments (None = unlimited)
    # Set to an integer to limit reply depth (e.g., 3 for up to 3 levels)
    'MAX_COMMENT_DEPTH': 3,
}
```

**Description:** Controls how deep comment threads can go.

**Options:**
- `None`: Unlimited nesting
- Integer (e.g., `3`): Limit nesting to N levels

---

## Content Settings

```python
DJANGO_COMMENTS_CONFIG = {
    # Maximum allowed length for comment content (in characters)
    'MAX_COMMENT_LENGTH': 3000,
    
    # Allow anonymous comments
    # If True, unauthenticated users can post comments with email/name
    # If False, only authenticated users can comment
    'ALLOW_ANONYMOUS': True,
    
    # Comment format ('plain', 'markdown', 'html')
    # - 'plain': Plain text with HTML escaped (safest)
    # - 'markdown': Markdown syntax supported (requires markdown package)
    # - 'html': HTML allowed with sanitization (requires bleach package)
    'COMMENT_FORMAT': 'plain',
}
```

**Format Options:**
- **plain**: Safe default, all HTML escaped
- **markdown**: Supports Markdown syntax (install: `pip install markdown`)
- **html**: Allows HTML with sanitization (install: `pip install bleach`)

---

## Sorting & Display

```python
DJANGO_COMMENTS_CONFIG = {
    # Default sort order for comments
    # Options: '-created_at', 'created_at', '-updated_at', 'updated_at'
    'DEFAULT_SORT': '-created_at',
    
    # List of allowed sort orders (enforced in API)
    # Users can only sort by these fields, prevents invalid queries
    'ALLOWED_SORTS': [
        '-created_at',
        'created_at',
        '-updated_at',
        'updated_at',
    ],
}
```

**Sorting Options:**
- `-created_at`: Newest first (default)
- `created_at`: Oldest first
- `-updated_at`: Recently updated first
- `updated_at`: Least recently updated first

---

## API Pagination

```python
DJANGO_COMMENTS_CONFIG = {
    # Number of comments per page (integrates with DRF pagination)
    'PAGE_SIZE': 20,
    
    # Allow client to specify page size via query parameter
    'PAGE_SIZE_QUERY_PARAM': 'page_size',
    
    # Maximum page size that can be requested
    'MAX_PAGE_SIZE': 100,
}
```

**Usage Example:**
```http
GET /api/comments/?page=2&page_size=50
```

---

## API Rate Limiting

```python
DJANGO_COMMENTS_CONFIG = {
    # Rate limit for authenticated users
    # Format: 'number/period' (e.g., '100/day', '10/hour', '5/minute')
    'API_RATE_LIMIT': '100/day',
    
    # Rate limit for anonymous users (typically lower)
    'API_RATE_LIMIT_ANON': '20/day',
    
    # Burst rate limit (short-term limit to prevent rapid spam)
    'API_RATE_LIMIT_BURST': '5/min',
}
```

**Rate Limit Periods:**
- `/second` or `/sec`
- `/minute` or `/min`
- `/hour`
- `/day`

**Example Configurations:**
```python
# Strict limits
'API_RATE_LIMIT': '50/day',
'API_RATE_LIMIT_BURST': '3/min',

# Permissive limits
'API_RATE_LIMIT': '1000/day',
'API_RATE_LIMIT_BURST': '10/min',
```

---

## Notifications

```python
DJANGO_COMMENTS_CONFIG = {
    # Enable email notifications
    'SEND_NOTIFICATIONS': False,
    
    # Use Celery for async notifications (requires celery to be installed)
    # When True, notifications are sent asynchronously via Celery tasks
    # When False (default), notifications are sent synchronously
    # Gracefully falls back to sync if Celery is not available
    'USE_ASYNC_NOTIFICATIONS': False,
    
    # Email subject template (can use {object} placeholder)
    'NOTIFICATION_SUBJECT': 'New comment on {object}',
    
    # Email templates for different notification types
    'NOTIFICATION_EMAIL_TEMPLATE': 'django_comments/email/new_comment.html',
    'NOTIFICATION_REPLY_TEMPLATE': 'django_comments/email/comment_reply.html',
    'NOTIFICATION_APPROVED_TEMPLATE': 'django_comments/email/comment_approved.html',
    'NOTIFICATION_REJECTED_TEMPLATE': 'django_comments/email/comment_rejected.html',
    'NOTIFICATION_MODERATOR_TEMPLATE': 'django_comments/email/moderator_notification.html',
    'NOTIFICATION_USER_BAN_TEMPLATE': 'django_comments/email/user_banned.html',
    'NOTIFICATION_USER_UNBAN_TEMPLATE': 'django_comments/email/user_unbanned.html',  
    'NOTIFICATION_FLAG_TEMPLATE': 'django_comments/email/moderator_flag_notification.html',
    
    # Email configuration (falls back to Django settings if None)
    'DEFAULT_FROM_EMAIL': None,  # Uses Django's DEFAULT_FROM_EMAIL if None
    
    # List of additional emails to notify about new comments
    'COMMENT_NOTIFICATION_EMAILS': [],
    
    # Site configuration (falls back to Site framework if None)
    'SITE_DOMAIN': None,  # Uses Site framework domain if None
    'SITE_NAME': None,  # Uses Site framework name if None
    'USE_HTTPS': True,  # Whether to use HTTPS in email links
}
```

**Notification Types:**
1. **New Comment** - Sent when someone comments on content
2. **Reply** - Sent when someone replies to a comment
3. **Approved** - Sent when comment is approved by moderator
4. **Rejected** - Sent when comment is rejected by moderator
5. **Moderator Alert** - Sent to moderators for non-public comments
6. **User Ban** - Sent when user is banned
7. **User Unban** - Sent when ban is lifted
8. **Flag Alert** - Sent when comment is flagged

**Async Notifications with Celery:**
```python
# settings.py
DJANGO_COMMENTS_CONFIG = {
    'SEND_NOTIFICATIONS': True,
    'USE_ASYNC_NOTIFICATIONS': True,
}

# Celery will automatically be used if available
# Falls back to synchronous sending if Celery is not configured
```

---

## Cleanup Settings

```python
DJANGO_COMMENTS_CONFIG = {
    # Days after which to remove non-public comments (None = never cleanup)
    # Used by the cleanup_comments management command
    'CLEANUP_AFTER_DAYS': None,
}
```

**Usage:**
```bash
# Run cleanup manually
python manage.py cleanup_comments

# Or schedule in cron/celery
0 2 * * * python manage.py cleanup_comments  # Daily at 2 AM
```

---

## Logging

```python
DJANGO_COMMENTS_CONFIG = {
    # Logger name for django-comments
    'LOGGER_NAME': 'django_comments',
}
```

**Configure Django logging:**
```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'comments.log',
        },
    },
    'loggers': {
        'django_comments': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

---

## Spam Detection

```python
DJANGO_COMMENTS_CONFIG = {
    # Enable spam detection
    'SPAM_DETECTION_ENABLED': False,
    
    # List of words/phrases that trigger spam detection
    # Content containing these words will be flagged as spam
    'SPAM_WORDS': [],
    
    # Action to take when spam is detected
    # Options:
    #   'flag' - Allow comment but auto-flag as spam (recommended)
    #   'hide' - Reject comment (set is_public=False)
    #   'delete' - Reject comment completely
    'SPAM_ACTION': 'flag',
    
    # Custom spam detector function (optional)
    # Should be a callable that takes content string and returns (is_spam: bool, reason: str)
    # Example: 'myapp.spam.detect_spam'
    'SPAM_DETECTOR': None,
}
```

**Simple Word-Based Detection:**
```python
'SPAM_DETECTION_ENABLED': True,
'SPAM_WORDS': ['viagra', 'casino', 'lottery', 'prize'],
'SPAM_ACTION': 'flag',
```

**Custom ML-Based Detection:**
```python
# myapp/spam.py
def detect_spam(content):
    """
    Custom spam detection using ML model.
    
    Args:
        content (str): Comment content to check
        
    Returns:
        tuple: (is_spam: bool, reason: str)
    """
    # Your ML model prediction here
    prediction = my_ml_model.predict(content)
    
    if prediction['is_spam']:
        return True, f"Spam confidence: {prediction['confidence']}"
    return False, None

# settings.py
DJANGO_COMMENTS_CONFIG = {
    'SPAM_DETECTION_ENABLED': True,
    'SPAM_DETECTOR': 'myapp.spam.detect_spam',
}
```

---

## Profanity Filtering

```python
DJANGO_COMMENTS_CONFIG = {
    # Enable profanity filtering
    'PROFANITY_FILTERING': False,
    
    # List of words to filter
    'PROFANITY_LIST': [],
    
    # Action to take when profanity is detected
    # Options:
    #   'censor' - Replace profane words with asterisks (e.g., 'f***')
    #   'flag' - Allow comment but auto-flag as offensive
    #   'hide' - Reject comment (set is_public=False)
    #   'delete' - Reject comment completely
    'PROFANITY_ACTION': 'censor',
}
```

**Example Configuration:**
```python
'PROFANITY_FILTERING': True,
'PROFANITY_LIST': ['badword1', 'badword2', 'offensive'],
'PROFANITY_ACTION': 'censor',  # Converts to 'b*******'
```

**Actions:**
- **censor**: Replaces profanity with asterisks, allows comment
- **flag**: Allows comment but flags it for review
- **hide**: Rejects comment (sets `is_public=False`)
- **delete**: Completely rejects the comment

---

## Caching

```python
DJANGO_COMMENTS_CONFIG = {
    # Cache timeout in seconds (default: 1 hour)
    # Used by the built-in caching system for comment counts
    'CACHE_TIMEOUT': 3600,
}
```

**What's Cached:**
- Comment counts per object
- Thread structures
- Query results

---

## Flag Thresholds & Auto-Moderation

```python
DJANGO_COMMENTS_CONFIG = {
    # Auto-hide comments after N user flags
    'AUTO_HIDE_THRESHOLD': 3,
    
    # Auto-delete comments after N user flags (None = never auto-delete)
    'AUTO_DELETE_THRESHOLD': 10,
    
    # Notify moderators when comment receives N flags
    'FLAG_NOTIFICATION_THRESHOLD': 1,
    
    # Auto-hide ML-detected spam immediately
    'AUTO_HIDE_DETECTED_SPAM': True,
    
    # Auto-hide profanity when PROFANITY_ACTION='flag'
    'AUTO_HIDE_PROFANITY': False,
}
```

**Auto-Moderation Flow:**
1. User flags comment (spam/inappropriate/harassment)
2. Flag count increments
3. At `FLAG_NOTIFICATION_THRESHOLD` → Moderators notified
4. At `AUTO_HIDE_THRESHOLD` → Comment auto-hidden
5. At `AUTO_DELETE_THRESHOLD` → Comment auto-deleted

**Example - Aggressive Moderation:**
```python
'AUTO_HIDE_THRESHOLD': 2,  # Hide after 2 flags
'AUTO_DELETE_THRESHOLD': 5,  # Delete after 5 flags
'FLAG_NOTIFICATION_THRESHOLD': 1,  # Notify immediately
'AUTO_HIDE_DETECTED_SPAM': True,
```

**Example - Lenient Moderation:**
```python
'AUTO_HIDE_THRESHOLD': 10,
'AUTO_DELETE_THRESHOLD': None,  # Never auto-delete
'FLAG_NOTIFICATION_THRESHOLD': 5,
'AUTO_HIDE_DETECTED_SPAM': False,
```

---

## Trusted Users & Auto-Approval

```python
DJANGO_COMMENTS_CONFIG = {
    # Auto-approve users after N approved comments (None = disabled)
    'AUTO_APPROVE_AFTER_N_APPROVED': 5,
    
    # User groups that bypass moderation
    'TRUSTED_USER_GROUPS': ['Verified', 'Premium'],
}
```

**How It Works:**
- Users get auto-approved after their first N comments are approved
- Users in `TRUSTED_USER_GROUPS` always bypass moderation
- Complements `AUTO_APPROVE_GROUPS` (for staff/moderators)

**Example:**
```python
# User journey:
# 1. First 5 comments: Require moderation
# 2. After 5 approved comments: Auto-approved forever
'AUTO_APPROVE_AFTER_N_APPROVED': 5,

# Premium users skip moderation from the start
'TRUSTED_USER_GROUPS': ['Premium', 'Verified'],
```

---

## Flag Abuse Prevention

```python
DJANGO_COMMENTS_CONFIG = {
    # Maximum flags a user can create per day
    'MAX_FLAGS_PER_DAY': 20,
    
    # Maximum flags a user can create per hour
    'MAX_FLAGS_PER_HOUR': 5,
}
```

**Purpose:** Prevents users from abusing the flagging system.

**Behavior:**
- When limits exceeded, flag creation returns error
- Limits reset based on time window
- Staff/superusers exempt from limits

---

## Enhanced Notifications

```python
DJANGO_COMMENTS_CONFIG = {
    # Notify moderators when comment is flagged
    'NOTIFY_ON_FLAG': True,
    
    # Notify moderators when comment is auto-hidden
    'NOTIFY_ON_AUTO_HIDE': True,
}
```

**When Enabled:**
- `NOTIFY_ON_FLAG`: Email sent to moderators when any flag is created
- `NOTIFY_ON_AUTO_HIDE`: Email sent when comment is auto-hidden by threshold

---

## Comment Editing

```python
DJANGO_COMMENTS_CONFIG = {
    # Enable comment editing
    'ALLOW_COMMENT_EDITING': True,
    
    # Time window for editing (in seconds, None = unlimited)
    'EDIT_TIME_WINDOW': 3600,  # 1 hour
    
    # Track edit history
    'TRACK_EDIT_HISTORY': True,
}
```

**Edit Window Examples:**
```python
# 1 hour window
'EDIT_TIME_WINDOW': 3600,

# 24 hours
'EDIT_TIME_WINDOW': 86400,

# Unlimited editing
'EDIT_TIME_WINDOW': None,

# No editing allowed
'ALLOW_COMMENT_EDITING': False,
```

**Edit History:**
- When `TRACK_EDIT_HISTORY=True`, creates `CommentRevision` records
- Stores previous content before each edit
- Viewable by moderators in admin

---

## Moderation Queue

```python
DJANGO_COMMENTS_CONFIG = {
    # Page size for moderation queue
    'MODERATION_QUEUE_PAGE_SIZE': 50,
    
    # Days to keep moderation logs
    'MODERATION_LOG_RETENTION_DAYS': 90,
}
```

**Moderation Actions Logged:**
- Approve/Reject decisions
- Flag reviews
- User bans/unbans
- Bulk actions

---

## Ban System

```python
DJANGO_COMMENTS_CONFIG = {
    # Default ban duration in days (None = permanent)
    'DEFAULT_BAN_DURATION_DAYS': 30,
    
    # Auto-ban after N rejected comments
    'AUTO_BAN_AFTER_REJECTIONS': 5,
    
    # Auto-ban after N spam flags on user's comments
    'AUTO_BAN_AFTER_SPAM_FLAGS': 3,
}
```

**Auto-Ban Triggers:**
1. User accumulates N rejected comments → Auto-banned
2. User's comments receive N spam flags total → Auto-banned

**Example Scenarios:**
```python
# Strict auto-ban
'AUTO_BAN_AFTER_REJECTIONS': 3,
'AUTO_BAN_AFTER_SPAM_FLAGS': 2,
'DEFAULT_BAN_DURATION_DAYS': None,  # Permanent

# Lenient auto-ban
'AUTO_BAN_AFTER_REJECTIONS': 10,
'AUTO_BAN_AFTER_SPAM_FLAGS': 5,
'DEFAULT_BAN_DURATION_DAYS': 7,  # 1 week
```

**Manual Ban API:**
```python
from django_comments.models import BannedUser
from datetime import timedelta
from django.utils import timezone

# Temporary ban
BannedUser.objects.create(
    user=problem_user,
    banned_until=timezone.now() + timedelta(days=30),
    reason="Repeated spam",
    banned_by=moderator
)

# Permanent ban
BannedUser.objects.create(
    user=problem_user,
    banned_until=None,  # Permanent
    reason="Severe harassment",
    banned_by=moderator
)
```

---

## GDPR Compliance

```python
DJANGO_COMMENTS_CONFIG = {
    # Enable GDPR compliance features
    # Set to True to enable anonymization and data export features
    'GDPR_ENABLED': True,
    
    # Data retention policy
    # Enable automatic anonymization of old personal data
    'GDPR_ENABLE_RETENTION_POLICY': False,  # Must be explicitly enabled
    'GDPR_RETENTION_DAYS': 365,  # Days before personal data is anonymized
    
    # Anonymization settings
    # Controls how data is anonymized during retention
    'GDPR_ANONYMIZE_IP_ON_RETENTION': True,  # Anonymize IPs (192.168.1.100 -> 192.168.1.0)
    'GDPR_ANONYMIZE_ON_USER_DELETE': True,  # Anonymize comments when user deleted
    
    # Data subject rights (GDPR Articles 15, 17, 20)
    'GDPR_ALLOW_USER_DATA_EXPORT': True,  # Article 20: Right to data portability
    'GDPR_ALLOW_USER_DATA_DELETION': True,  # Article 17: Right to erasure
    
    # Data collection transparency (GDPR Article 13)
    # Disable these if you don't want to collect this personal data
    'GDPR_COLLECT_IP_ADDRESS': True,  # Set to False to not collect IPs at all
    'GDPR_COLLECT_USER_AGENT': True,  # Set to False to not collect user agents
}
```

**GDPR Features:**

### Data Export (Right to Portability)
```python
from django_comments.gdpr import export_user_data

data = export_user_data(user)
# Returns JSON with all user's comment data
```

### Data Deletion (Right to Erasure)
```python
from django_comments.gdpr import anonymize_user_data

anonymize_user_data(user)
# Anonymizes: username, email, IP addresses, user agent
```

### Automatic Retention Policy
```python
# Enable automatic anonymization after 1 year
'GDPR_ENABLE_RETENTION_POLICY': True,
'GDPR_RETENTION_DAYS': 365,

# Run via management command or celery
python manage.py anonymize_old_comments
```

### Privacy-First Configuration
```python
# Don't collect personal data
'GDPR_COLLECT_IP_ADDRESS': False,
'GDPR_COLLECT_USER_AGENT': False,

# Auto-anonymize on user deletion
'GDPR_ANONYMIZE_ON_USER_DELETE': True,
```

---

## Complete Example Configuration

```python
# settings.py

DJANGO_COMMENTS_CONFIG = {
    # Models
    'COMMENTABLE_MODELS': ['blog.Post', 'products.Product'],
    
    # Moderation
    'MODERATOR_REQUIRED': True,
    'AUTO_APPROVE_GROUPS': ['Moderators', 'Staff'],
    'AUTO_APPROVE_AFTER_N_APPROVED': 5,
    'TRUSTED_USER_GROUPS': ['Premium'],
    
    # Content
    'MAX_COMMENT_LENGTH': 3000,
    'ALLOW_ANONYMOUS': False,
    'COMMENT_FORMAT': 'markdown',
    'MAX_COMMENT_DEPTH': 3,
    
    # Spam & Profanity
    'SPAM_DETECTION_ENABLED': True,
    'SPAM_WORDS': ['viagra', 'casino'],
    'SPAM_ACTION': 'flag',
    'PROFANITY_FILTERING': True,
    'PROFANITY_LIST': ['badword'],
    'PROFANITY_ACTION': 'censor',
    
    # Auto-Moderation
    'AUTO_HIDE_THRESHOLD': 3,
    'AUTO_DELETE_THRESHOLD': 10,
    'FLAG_NOTIFICATION_THRESHOLD': 1,
    'AUTO_HIDE_DETECTED_SPAM': True,
    
    # Bans
    'AUTO_BAN_AFTER_REJECTIONS': 5,
    'AUTO_BAN_AFTER_SPAM_FLAGS': 3,
    'DEFAULT_BAN_DURATION_DAYS': 30,
    
    # Notifications
    'SEND_NOTIFICATIONS': True,
    'USE_ASYNC_NOTIFICATIONS': True,
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
}
```

---

## Management Commands

### Cleanup Comments
```bash
python manage.py cleanup_comments
# Removes non-public comments older than CLEANUP_AFTER_DAYS
```

### Anonymize Old Comments (GDPR)
```bash
python manage.py anonymize_old_comments
# Anonymizes personal data older than GDPR_RETENTION_DAYS
```

### Moderation Queue
```bash
python manage.py show_moderation_queue
# Displays comments pending moderation
```

---

## Signal Reference

Available signals for custom integrations:

```python
from django_comments.signals import (
    comment_created,        # Fired when comment is created
    comment_updated,        # Fired when comment is updated
    comment_deleted,        # Fired when comment is deleted
    comment_flagged,        # Fired when comment is flagged
    comment_approved,       # Fired when comment is approved
    comment_rejected,       # Fired when comment is rejected
    user_banned,            # Fired when user is banned
    user_unbanned,          # Fired when user is unbanned
)

# Example usage
@receiver(comment_created)
def my_comment_handler(sender, instance, **kwargs):
    print(f"New comment: {instance.content}")
```

---

## Environment-Specific Configurations

### Development
```python
DJANGO_COMMENTS_CONFIG = {
    'MODERATOR_REQUIRED': False,  # Fast testing
    'SEND_NOTIFICATIONS': False,  # Don't spam emails
    'SPAM_DETECTION_ENABLED': False,
    'API_RATE_LIMIT': '1000/day',  # High limits
}
```

### Staging
```python
DJANGO_COMMENTS_CONFIG = {
    'MODERATOR_REQUIRED': True,
    'SEND_NOTIFICATIONS': True,
    'SPAM_DETECTION_ENABLED': True,
    'API_RATE_LIMIT': '100/day',
    'USE_ASYNC_NOTIFICATIONS': True,
}
```

### Production
```python
DJANGO_COMMENTS_CONFIG = {
    'MODERATOR_REQUIRED': True,
    'SEND_NOTIFICATIONS': True,
    'USE_ASYNC_NOTIFICATIONS': True,
    'SPAM_DETECTION_ENABLED': True,
    'SPAM_DETECTOR': 'myapp.ml.detect_spam',  # ML-based
    'PROFANITY_FILTERING': True,
    'AUTO_HIDE_THRESHOLD': 3,
    'AUTO_BAN_AFTER_SPAM_FLAGS': 3,
    'API_RATE_LIMIT': '100/day',
    'API_RATE_LIMIT_ANON': '20/day',
    'GDPR_ENABLED': True,
    'GDPR_ENABLE_RETENTION_POLICY': True,
}
```

---

**Need Help?** Check the [full documentation](https://django-reusable-comments.readthedocs.io/) or [open an issue](https://github.com/NzeStan/django-reusable-comments/issues).