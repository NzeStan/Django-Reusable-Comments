# Advanced Usage Guide

This guide covers advanced features, integration patterns, best practices, and real-world use cases for django-reusable-comments.

## Table of Contents

- [Custom Spam Detection](#custom-spam-detection)
- [Email Notifications](#email-notifications)
- [Signals & Hooks](#signals--hooks)
- [Template Tags](#template-tags)
- [Management Commands](#management-commands)
- [GDPR Compliance](#gdpr-compliance)
- [Performance Optimization](#performance-optimization)
- [Security Best Practices](#security-best-practices)
- [Frontend Integration](#frontend-integration)
- [Real-World Examples](#real-world-examples)

---

## Custom Spam Detection

### Basic Word-Based Detection

```python
# settings.py
DJANGO_COMMENTS_CONFIG = {
    'SPAM_DETECTION_ENABLED': True,
    'SPAM_WORDS': [
        'viagra', 'casino', 'lottery', 'prize',
        'click here', 'buy now', 'limited time',
        'make money fast', 'work from home'
    ],
    'SPAM_ACTION': 'flag',  # 'flag', 'hide', or 'delete'
}
```

### Machine Learning Integration

Create a custom ML-based spam detector:

```python
# myapp/spam_detector.py
import joblib
import re
from typing import Tuple

# Load pre-trained model and vectorizer
model = joblib.load('path/to/spam_classifier.pkl')
vectorizer = joblib.load('path/to/tfidf_vectorizer.pkl')

def detect_spam(content: str) -> Tuple[bool, str]:
    """
    Detect spam using ML model.
    
    Args:
        content: Comment text to analyze
        
    Returns:
        (is_spam: bool, reason: str)
    """
    # Preprocess content
    content_clean = content.lower().strip()
    
    # Extract features
    features = vectorizer.transform([content_clean])
    
    # Predict
    prediction = model.predict(features)[0]
    probability = model.predict_proba(features)[0]
    
    if prediction == 1:  # Spam
        confidence = probability[1] * 100
        return True, f"Spam detected (confidence: {confidence:.1f}%)"
    
    return False, None

# Advanced version with multiple signals
def advanced_detect_spam(content: str) -> Tuple[bool, str]:
    """Advanced spam detection with multiple heuristics."""
    
    # Signal 1: ML prediction
    features = vectorizer.transform([content])
    ml_score = model.predict_proba(features)[0][1]
    
    # Signal 2: URL count
    url_count = len(re.findall(r'http[s]?://', content))
    
    # Signal 3: Caps ratio
    caps_ratio = sum(1 for c in content if c.isupper()) / max(len(content), 1)
    
    # Signal 4: Exclamation marks
    exclaim_count = content.count('!')
    
    # Combined scoring
    spam_score = (
        ml_score * 0.5 +
        min(url_count / 3, 1) * 0.2 +
        min(caps_ratio * 2, 1) * 0.2 +
        min(exclaim_count / 5, 1) * 0.1
    )
    
    if spam_score > 0.6:
        return True, f"Spam score: {spam_score:.2f}"
    
    return False, None
```

Configure in settings:

```python
# settings.py
DJANGO_COMMENTS_CONFIG = {
    'SPAM_DETECTION_ENABLED': True,
    'SPAM_DETECTOR': 'myapp.spam_detector.advanced_detect_spam',
    'SPAM_ACTION': 'hide',
}
```

### Training Your Own Model

```python
# training/train_spam_model.py
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
import joblib

# Load training data
df = pd.read_csv('comment_labels.csv')
# Columns: 'content', 'is_spam' (1 for spam, 0 for ham)

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    df['content'], df['is_spam'], test_size=0.2, random_state=42
)

# Create TF-IDF features
vectorizer = TfidfVectorizer(
    max_features=5000,
    ngram_range=(1, 2),
    stop_words='english'
)
X_train_tfidf = vectorizer.fit_transform(X_train)
X_test_tfidf = vectorizer.transform(X_test)

# Train classifier
model = MultinomialNB()
model.fit(X_train_tfidf, y_train)

# Evaluate
accuracy = model.score(X_test_tfidf, y_test)
print(f"Accuracy: {accuracy:.2%}")

# Save model
joblib.dump(model, 'spam_classifier.pkl')
joblib.dump(vectorizer, 'tfidf_vectorizer.pkl')
```

---

## Email Notifications

### Setup Email Backend

```python
# settings.py

# Gmail SMTP
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'  # Use app-specific password
DEFAULT_FROM_EMAIL = 'noreply@yourdomain.com'

# SendGrid
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = 'your-sendgrid-api-key'

# AWS SES
EMAIL_BACKEND = 'django_ses.SESBackend'
AWS_ACCESS_KEY_ID = 'your-access-key'
AWS_SECRET_ACCESS_KEY = 'your-secret-key'
AWS_SES_REGION_NAME = 'us-east-1'
AWS_SES_REGION_ENDPOINT = 'email.us-east-1.amazonaws.com'
```

### Custom Email Templates

Override default templates by creating your own:

```django
{# templates/django_comments/emails/new_comment.html #}
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: #4CAF50;
            color: white;
            padding: 20px;
            text-align: center;
        }
        .content {
            background: #f9f9f9;
            padding: 20px;
            margin: 20px 0;
        }
        .comment {
            background: white;
            border-left: 4px solid #4CAF50;
            padding: 15px;
            margin: 15px 0;
        }
        .button {
            display: inline-block;
            background: #4CAF50;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>New Comment on Your Post</h1>
        </div>
        
        <div class="content">
            <p>Hi {{ recipient_name }},</p>
            
            <p>
                <strong>{{ comment.user.get_full_name|default:comment.user.username }}</strong>
                commented on "{{ content_object }}":
            </p>
            
            <div class="comment">
                {{ comment.formatted_content|safe }}
            </div>
            
            <p>
                <a href="{{ comment_url }}" class="button">View Comment</a>
            </p>
            
            <p>
                Posted on {{ comment.created_at|date:"F j, Y \a\t g:i A" }}
            </p>
        </div>
        
        <div style="text-align: center; color: #999; font-size: 12px;">
            <p>
                You're receiving this because you're the author of the content.
                <br>
                <a href="{{ unsubscribe_url }}">Unsubscribe from notifications</a>
            </p>
        </div>
    </div>
</body>
</html>
```

```django
{# templates/django_comments/emails/new_comment.txt #}
Hi {{ recipient_name }},

{{ comment.user.get_full_name|default:comment.user.username }} commented on "{{ content_object }}":

---
{{ comment.content }}
---

View the comment: {{ comment_url }}

Posted on {{ comment.created_at|date:"F j, Y \a\t g:i A" }}

---
You're receiving this because you're the author of the content.
Unsubscribe: {{ unsubscribe_url }}
```

### Configure Templates in Settings

```python
# settings.py
DJANGO_COMMENTS_CONFIG = {
    'SEND_NOTIFICATIONS': True,
    
    # Custom template paths
    'NOTIFICATION_EMAIL_TEMPLATE': 'myapp/emails/new_comment.html',
    'NOTIFICATION_REPLY_TEMPLATE': 'myapp/emails/comment_reply.html',
    'NOTIFICATION_APPROVED_TEMPLATE': 'myapp/emails/approved.html',
    'NOTIFICATION_REJECTED_TEMPLATE': 'myapp/emails/rejected.html',
    'NOTIFICATION_MODERATOR_TEMPLATE': 'myapp/emails/moderator_alert.html',
    'NOTIFICATION_USER_BAN_TEMPLATE': 'myapp/emails/banned.html',
    'NOTIFICATION_USER_UNBAN_TEMPLATE': 'myapp/emails/unbanned.html',
    'NOTIFICATION_FLAG_TEMPLATE': 'myapp/emails/flag_alert.html',
    
    # Email recipients
    'COMMENT_NOTIFICATION_EMAILS': [
        'moderators@example.com',
        'admin@example.com',
    ],
}
```

### Async Notifications (Built-in Threading)

Async notifications use Python's built-in `threading.Thread` — no Celery, Redis, or external broker is needed. Each notification is dispatched as a fire-and-forget daemon thread so the HTTP response is never blocked.

```python
# settings.py
DJANGO_COMMENTS_CONFIG = {
    'SEND_NOTIFICATIONS': True,
    'USE_ASYNC_NOTIFICATIONS': True,  # dispatches in a daemon Thread
}
```

Failures are logged via the `django_comments` logger but not automatically retried. For guaranteed delivery in high-volume environments, consider wrapping notification calls in a persistent task queue (Celery, RQ, etc.) of your choice.

---

## Signals & Hooks

### Available Signals

```python
from django_comments.signals import (
    comment_pre_save,      # Before comment is saved
    comment_post_save,     # After comment is saved
    comment_pre_delete,    # Before comment is deleted
    comment_post_delete,   # After comment is deleted
    comment_flagged,       # When comment is flagged
    comment_approved,      # When comment is approved
    comment_rejected,      # When comment is rejected
)
```

### Signal Usage Examples

#### 1. Send Custom Notifications

```python
# myapp/signals.py
from django.dispatch import receiver
from django_comments.signals import comment_post_save
from django.core.mail import send_mail

@receiver(comment_post_save)
def notify_slack_on_comment(sender, comment, created, **kwargs):
    """Send Slack notification for new comments."""
    if not created:
        return
    
    import requests
    
    webhook_url = 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
    
    message = {
        'text': f'New comment by {comment.user.username}',
        'blocks': [
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f'*New Comment*\n{comment.content[:200]}'
                }
            },
            {
                'type': 'actions',
                'elements': [
                    {
                        'type': 'button',
                        'text': {'type': 'plain_text', 'text': 'View'},
                        'url': f'https://example.com/comments/{comment.id}/'
                    }
                ]
            }
        ]
    }
    
    requests.post(webhook_url, json=message)
```

#### 2. Update User Statistics

```python
@receiver(comment_post_save)
def update_user_comment_count(sender, comment, created, **kwargs):
    """Update user profile comment count."""
    if not created:
        return
    
    profile = comment.user.profile
    profile.total_comments = profile.total_comments + 1
    profile.last_comment_at = comment.created_at
    profile.save(update_fields=['total_comments', 'last_comment_at'])
```

#### 3. Award Points/Badges

```python
@receiver(comment_post_save)
def award_commenter_badge(sender, comment, created, **kwargs):
    """Award badges based on comment milestones."""
    if not created:
        return
    
    from myapp.models import Badge
    
    comment_count = comment.user.comments.count()
    
    # Award badges at milestones
    badges_to_award = []
    
    if comment_count == 1:
        badges_to_award.append('First Comment')
    elif comment_count == 10:
        badges_to_award.append('Active Commenter')
    elif comment_count == 100:
        badges_to_award.append('Comment Master')
    
    for badge_name in badges_to_award:
        badge, created = Badge.objects.get_or_create(
            user=comment.user,
            name=badge_name
        )
```

#### 4. Content Moderation Integration

```python
@receiver(comment_post_save)
def send_to_moderation_queue(sender, comment, created, **kwargs):
    """Send new comments to third-party moderation service."""
    if not created or comment.is_public:
        return
    
    import requests
    
    # Send to external moderation API
    response = requests.post(
        'https://moderation-api.example.com/analyze',
        json={
            'content': comment.content,
            'user_id': str(comment.user.id),
            'callback_url': f'https://yourdomain.com/api/moderation-callback/'
        },
        headers={'Authorization': 'Bearer YOUR_API_KEY'}
    )
```

#### 5. Analytics Tracking

```python
@receiver(comment_post_save)
def track_comment_analytics(sender, comment, created, **kwargs):
    """Track comment events in analytics platform."""
    if not created:
        return
    
    from myapp.analytics import track_event
    
    track_event('comment_created', {
        'user_id': comment.user.id,
        'content_type': str(comment.content_type),
        'object_id': comment.object_id,
        'has_parent': comment.parent is not None,
        'depth': comment.depth,
    })
```

#### 6. Auto-Flag Suspicious Content

```python
@receiver(comment_post_save)
def auto_flag_suspicious_content(sender, comment, created, **kwargs):
    """Automatically flag comments with suspicious patterns."""
    if not created:
        return
    
    import re
    
    # Check for suspicious patterns
    suspicious = False
    reason = []
    
    # Too many URLs
    url_count = len(re.findall(r'http[s]?://', comment.content))
    if url_count > 3:
        suspicious = True
        reason.append(f'{url_count} URLs detected')
    
    # All caps
    if comment.content.isupper() and len(comment.content) > 20:
        suspicious = True
        reason.append('All caps content')
    
    # Too many exclamation marks
    exclaim_count = comment.content.count('!')
    if exclaim_count > 5:
        suspicious = True
        reason.append(f'{exclaim_count} exclamation marks')
    
    if suspicious:
        from django_comments.models import CommentFlag
        from django_comments.utils import get_or_create_system_user
        
        system_user = get_or_create_system_user()
        
        CommentFlag.objects.create(
            comment=comment,
            user=system_user,
            flag='spam',
            reason=f"Auto-flagged: {', '.join(reason)}"
        )
```

### Register Signal Handlers

```python
# myapp/apps.py
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'
    
    def ready(self):
        import myapp.signals  # Import to register receivers
```

```python
# myapp/__init__.py
default_app_config = 'myapp.apps.MyAppConfig'
```

---

## Template Tags

### Loading Template Tags

```django
{% load comment_tags %}
```

### Get Comment Count

```django
{# Get count and display #}
{% get_comment_count article as comment_count %}
<p>{{ comment_count }} comment{{ comment_count|pluralize }}</p>

{# Public comments only #}
{% get_comment_count article public_only=True as public_count %}

{# All comments (including non-public) #}
{% get_comment_count article public_only=False as all_count %}
```

### Check for Comments

```django
{% has_comments article as has_any_comments %}
{% if has_any_comments %}
    <div class="comments-section">
        {# Show comments #}
    </div>
{% else %}
    <p>No comments yet. Be the first to comment!</p>
{% endif %}
```

### List Comments

```django
{# Get all comments #}
{% get_comments article as comments %}

{# Get root comments only (no replies) #}
{% get_root_comments article as root_comments %}

{# Get with custom ordering #}
{% get_comments article ordering="-created_at" as recent_comments %}

{# Display comments #}
{% for comment in comments %}
    <div class="comment" id="comment-{{ comment.id }}">
        <div class="comment-header">
            <strong>{{ comment.user.get_full_name|default:comment.user.username }}</strong>
            <span class="comment-date">{{ comment.created_at|timesince }} ago</span>
        </div>
        <div class="comment-content">
            {{ comment.formatted_content|safe }}
        </div>
        
        {# Show replies #}
        {% if comment.children.all %}
            <div class="comment-replies">
                {% for reply in comment.children.all %}
                    <div class="comment reply">
                        <strong>{{ reply.user.username }}</strong>: {{ reply.content }}
                    </div>
                {% endfor %}
            </div>
        {% endif %}
    </div>
{% endfor %}
```

### Threaded Comments Display

```django
{# Recursive template for threaded comments #}
{# comments.html #}
{% load comment_tags %}

<div class="comments-container">
    {% get_root_comments article as root_comments %}
    
    {% for comment in root_comments %}
        {% include "comments/comment_thread.html" with comment=comment depth=0 %}
    {% endfor %}
</div>

{# comment_thread.html #}
<div class="comment depth-{{ depth }}" id="comment-{{ comment.id }}" 
     style="margin-left: {{ depth|add:"0" }}rem;">
    <div class="comment-header">
        <img src="{{ comment.user.profile.avatar_url }}" alt="{{ comment.user.username }}" 
             class="avatar">
        <strong>{{ comment.user.get_full_name|default:comment.user.username }}</strong>
        
        {% if comment.user_info.is_moderator %}
            <span class="badge badge-moderator">Moderator</span>
        {% endif %}
        
        <span class="comment-date">{{ comment.created_at|timesince }} ago</span>
        
        {% if comment.updated_at > comment.created_at %}
            <span class="edited">(edited)</span>
        {% endif %}
    </div>
    
    <div class="comment-content">
        {{ comment.formatted_content|safe }}
    </div>
    
    <div class="comment-actions">
        <a href="{% url 'reply_comment' comment.id %}">Reply</a>
        
        {% if comment.user == request.user %}
            <a href="{% url 'edit_comment' comment.id %}">Edit</a>
            <a href="{% url 'delete_comment' comment.id %}">Delete</a>
        {% endif %}
        
        {% if perms.django_comments.can_moderate_comments %}
            {% if not comment.is_public %}
                <a href="{% url 'approve_comment' comment.id %}">Approve</a>
            {% endif %}
            <a href="{% url 'reject_comment' comment.id %}">Remove</a>
        {% endif %}
        
        <a href="{% url 'flag_comment' comment.id %}">Flag</a>
    </div>
    
    {# Recursive: Show nested replies #}
    {% if comment.children.all and depth < 5 %}
        <div class="comment-replies">
            {% for reply in comment.children.all %}
                {% include "comments/comment_thread.html" with comment=reply depth=depth|add:"1" %}
            {% endfor %}
        </div>
    {% endif %}
</div>
```

### Format Comment Content

```django
{# Format with different types #}
{{ comment.content|format_comment:"plain" }}
{{ comment.content|format_comment:"markdown" }}
{{ comment.content|format_comment:"html" }}

{# Truncate comments #}
{{ comment.content|truncate_comment:150 }}
```

### User Comment Count

```django
{# Get count for current user #}
{% get_user_comment_count as my_comment_count %}
<p>You've made {{ my_comment_count }} comments</p>

{# Get count for specific user #}
{% get_user_comment_count user=article.author as author_comment_count %}
```

### Check Permissions

```django
{# Check if user can comment #}
{% can_comment user article as can_post_comment %}
{% if can_post_comment %}
    <a href="{% url 'add_comment' %}">Add Comment</a>
{% else %}
    <p>Please log in to comment.</p>
{% endif %}
```

---

## Management Commands

### Cleanup Old Comments

```bash
# Remove non-public comments older than 30 days
python manage.py cleanup_comments --days 30

# Remove spam comments
python manage.py cleanup_comments --spam

# Remove flagged comments
python manage.py cleanup_comments --flagged

# Dry run (show what would be deleted)
python manage.py cleanup_comments --days 30 --dry-run

# Verbose output
python manage.py cleanup_comments --days 30 --verbose
```

### Anonymize Old Comments (GDPR)

```bash
# Anonymize comments older than retention period
python manage.py enforce_gdpr_retention

# Dry run
python manage.py enforce_gdpr_retention --dry-run

# Verbose output
python manage.py enforce_gdpr_retention --verbose
```

### Show Moderation Queue

```bash
# Show pending comments
python manage.py show_moderation_queue

# Show with details
python manage.py show_moderation_queue --verbose
```

### Custom Management Commands

Create your own:

```python
# myapp/management/commands/export_comments.py
from django.core.management.base import BaseCommand
from django_comments.models import Comment
import json
from datetime import datetime

class Command(BaseCommand):
    help = 'Export comments to JSON'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--since',
            type=str,
            help='Export comments since date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='comments_export.json',
            help='Output file path',
        )
    
    def handle(self, *args, **options):
        queryset = Comment.objects.all()
        
        if options['since']:
            since_date = datetime.strptime(options['since'], '%Y-%m-%d')
            queryset = queryset.filter(created_at__gte=since_date)
        
        comments_data = []
        for comment in queryset:
            comments_data.append({
                'id': str(comment.id),
                'content': comment.content,
                'user': comment.user.username,
                'created_at': comment.created_at.isoformat(),
                'is_public': comment.is_public,
            })
        
        with open(options['output'], 'w') as f:
            json.dump(comments_data, f, indent=2)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Exported {len(comments_data)} comments to {options["output"]}'
            )
        )
```

Usage:

```bash
python manage.py export_comments --since 2025-01-01 --output recent_comments.json
```

---

## GDPR Compliance

### Data Export

```python
from django_comments.gdpr import export_user_data

# Export all user's data
data = export_user_data(user)

# Returns dictionary with:
# - comments
# - flags
# - moderation_actions
# - export_date

# Save to JSON file
import json
with open(f'user_{user.id}_data.json', 'w') as f:
    json.dump(data, f, indent=2)

# Send to user via email
from django.core.mail import EmailMessage
from django.core.serializers.json import DjangoJSONEncoder

email = EmailMessage(
    subject='Your Data Export',
    body='Attached is your requested data export.',
    from_email='noreply@example.com',
    to=[user.email],
)
email.attach(
    f'data_export_{user.username}.json',
    json.dumps(data, indent=2, cls=DjangoJSONEncoder),
    'application/json'
)
email.send()
```

### Data Anonymization

```python
from django_comments.gdpr import anonymize_user_data

# Anonymize all user's comments
anonymize_user_data(user)

# This will:
# - Replace user with anonymous user
# - Clear IP addresses
# - Clear user agent strings
# - Preserve comment content
```

### Automatic Anonymization

```python
# settings.py
DJANGO_COMMENTS_CONFIG = {
    'GDPR_ENABLED': True,
    
    # Auto-anonymize when user account is deleted
    'GDPR_ANONYMIZE_ON_USER_DELETE': True,
    
    # Retention policy
    'GDPR_ENABLE_RETENTION_POLICY': True,
    'GDPR_RETENTION_DAYS': 365,  # Anonymize after 1 year
    
    # What to anonymize
    'GDPR_ANONYMIZE_IP_ON_RETENTION': True,
}
```

Schedule in cron:

```cron
# Run every Sunday at 2 AM
0 2 * * 0 cd /path/to/project && python manage.py enforce_gdpr_retention
```

### User-Initiated Deletion

Create a view for users to request deletion:

```python
# views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django_comments.gdpr import anonymize_user_data

@login_required
def request_data_deletion(request):
    if request.method == 'POST':
        if request.POST.get('confirm') == 'yes':
            # Anonymize user's comments
            anonymize_user_data(request.user)
            
            # Delete user account
            request.user.delete()
            
            messages.success(request, 'Your data has been deleted.')
            return redirect('home')
    
    return render(request, 'accounts/confirm_deletion.html')
```

---

## Performance Optimization

### Database Indexes

```python
# Migration to add custom indexes
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('django_comments', '0001_initial'),
    ]
    
    operations = [
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(
                fields=['content_type', 'object_id', '-created_at'],
                name='comment_object_created_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(
                fields=['user', '-created_at'],
                name='comment_user_created_idx'
            ),
        ),
    ]
```

### Query Optimization

```python
# Use select_related for foreign keys
comments = Comment.objects.select_related(
    'user',
    'content_type',
    'parent'
).filter(object_id=article.id)

# Use prefetch_related for reverse relations
from django.db.models import Prefetch

comments = Comment.objects.prefetch_related(
    Prefetch(
        'children',
        queryset=Comment.objects.select_related('user')
    ),
    'flags',
    'revisions'
).filter(is_public=True)

# Annotate with counts
from django.db.models import Count

comments = Comment.objects.annotate(
    reply_count=Count('children'),
    flag_count=Count('flags')
).filter(is_public=True)
```

### Caching

```python
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType

def get_comment_count_cached(obj):
    """Get comment count with caching."""
    ct = ContentType.objects.get_for_model(obj)
    cache_key = f'comment_count_{ct.id}_{obj.pk}'
    
    count = cache.get(cache_key)
    if count is None:
        count = Comment.objects.filter(
            content_type=ct,
            object_id=obj.pk,
            is_public=True
        ).count()
        cache.set(cache_key, count, timeout=3600)  # 1 hour
    
    return count

# Invalidate cache on save
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Comment)
def invalidate_comment_count_cache(sender, instance, **kwargs):
    ct = instance.content_type
    cache_key = f'comment_count_{ct.id}_{instance.object_id}'
    cache.delete(cache_key)
```

### Pagination Performance

```python
# Use keyset pagination for large datasets
from rest_framework.pagination import CursorPagination

class CommentCursorPagination(CursorPagination):
    page_size = 20
    ordering = '-created_at'

# In viewset
class CommentViewSet(viewsets.ModelViewSet):
    pagination_class = CommentCursorPagination
```

### Database Connection Pooling

```python
# settings.py (PostgreSQL with pgbouncer)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_db',
        'USER': 'your_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '6432',  # PgBouncer port
        'CONN_MAX_AGE': 600,  # Connection pooling
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}
```

---

## Security Best Practices

### Rate Limiting Configuration

```python
# settings.py

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/day',
        'user': '100/day',
        'comment_create': '10/hour',
        'flag_create': '5/hour',
    }
}

DJANGO_COMMENTS_CONFIG = {
    'API_RATE_LIMIT': '100/day',
    'API_RATE_LIMIT_ANON': '20/day',
    'API_RATE_LIMIT_BURST': '5/min',
}
```

### Content Security Policy

```python
# settings.py

# django-csp package
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")  # Avoid unsafe-inline in production
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "data:")
```

### HTTPS Enforcement

```python
# settings.py (production)

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

### Input Validation

Always validate and sanitize user input:

```python
from django_comments.formatting import render_comment_content

# When displaying HTML comments
safe_html = render_comment_content(comment, format_type='html')
# This uses bleach to sanitize HTML

# Configure allowed tags
DJANGO_COMMENTS_CONFIG = {
    'HTML_ALLOWED_TAGS': ['p', 'br', 'strong', 'em', 'a'],
    'HTML_ALLOWED_ATTRIBUTES': {'a': ['href', 'title']},
}
```

### XSS Prevention

```django
{# Always escape user content in templates #}
<div class="comment">
    {{ comment.content }}  {# Auto-escaped #}
</div>

{# Only use |safe for sanitized content #}
<div class="comment">
    {{ comment.formatted_content|safe }}  {# Already sanitized #}
</div>
```

---

## Frontend Integration

Django Reusable Comments supports two integration patterns:

1. **Generic endpoint** - Full control, suitable for admin interfaces
2. **Object-specific endpoint** - Simplified, secure pattern for public frontends (recommended)

---

### React Integration

#### Option 1: Using Generic Endpoint
```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const CommentList = ({ contentType, objectId }) => {
    const [comments, setComments] = useState([]);
    const [loading, setLoading] = useState(true);
    
    useEffect(() => {
        fetchComments();
    }, [contentType, objectId]);
    
    const fetchComments = async () => {
        try {
            const response = await axios.get('/api/comments/', {
                params: {
                    content_type: contentType,
                    object_id: objectId,
                    ordering: '-created_at'
                }
            });
            setComments(response.data.results);
        } catch (error) {
            console.error('Error fetching comments:', error);
        } finally {
            setLoading(false);
        }
    };
    
    const handleSubmit = async (content) => {
        try {
            const response = await axios.post(
                '/api/comments/',
                {
                    content_type: contentType,
                    object_id: objectId,
                    content: content
                },
                {
                    headers: {
                        'Authorization': `Token ${localStorage.getItem('token')}`
                    }
                }
            );
            setComments([response.data, ...comments]);
        } catch (error) {
            console.error('Error posting comment:', error);
        }
    };
    
    if (loading) return <div>Loading...</div>;
    
    return (
        <div className="comments">
            <CommentForm onSubmit={handleSubmit} />
            {comments.map(comment => (
                <Comment key={comment.id} comment={comment} />
            ))}
        </div>
    );
};

export default CommentList;

// Usage:
// <CommentList contentType="blog.post" objectId="123" />
```

---

#### Option 2: Using Object-Specific Endpoint (Recommended)
```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const CommentList = ({ appLabel, model, objectId }) => {
    const [comments, setComments] = useState([]);
    const [loading, setLoading] = useState(true);
    
    // Construct secure API URL from object metadata
    const apiUrl = `/api/${appLabel}/${model}/${objectId}/comments/`;
    
    useEffect(() => {
        fetchComments();
    }, [appLabel, model, objectId]);
    
    const fetchComments = async () => {
        try {
            const response = await axios.get(apiUrl, {
                params: {
                    ordering: '-created_at'
                }
            });
            setComments(response.data.results);
        } catch (error) {
            console.error('Error fetching comments:', error);
        } finally {
            setLoading(false);
        }
    };
    
    const handleSubmit = async (content) => {
        try {
            const response = await axios.post(
                apiUrl,
                {
                    content: content  // Only content - backend controls metadata
                },
                {
                    headers: {
                        'Authorization': `Token ${localStorage.getItem('token')}`
                    }
                }
            );
            setComments([response.data, ...comments]);
        } catch (error) {
            console.error('Error posting comment:', error);
        }
    };
    
    if (loading) return <div>Loading...</div>;
    
    return (
        <div className="comments">
            <CommentForm onSubmit={handleSubmit} />
            {comments.map(comment => (
                <Comment key={comment.id} comment={comment} />
            ))}
        </div>
    );
};

export default CommentList;

// Usage (note cleaner separation of object metadata):
// <CommentList appLabel="blog" model="post" objectId="123" />
```

**Why Option 2 is recommended for public frontends:**
- ✅ Enhanced security - backend controls all metadata
- ✅ Simpler component props - clear separation of concerns
- ✅ Prevents impersonation attacks
- ✅ Easier to understand URL structure

---

### Vue.js Integration

#### Option 1: Using Generic Endpoint
```vue
<template>
    <div class="comments">
        <comment-form @submit="addComment" />
        
        <div v-if="loading">Loading...</div>
        
        <comment-item
            v-for="comment in comments"
            :key="comment.id"
            :comment="comment"
            @reply="replyToComment"
        />
    </div>
</template>

<script>
import axios from 'axios';

export default {
    name: 'CommentList',
    props: {
        contentType: String,
        objectId: String
    },
    data() {
        return {
            comments: [],
            loading: true
        };
    },
    mounted() {
        this.fetchComments();
    },
    methods: {
        async fetchComments() {
            try {
                const response = await axios.get('/api/comments/', {
                    params: {
                        content_type: this.contentType,
                        object_id: this.objectId
                    }
                });
                this.comments = response.data.results;
            } catch (error) {
                console.error(error);
            } finally {
                this.loading = false;
            }
        },
        async addComment(content) {
            try {
                const response = await axios.post('/api/comments/', {
                    content_type: this.contentType,
                    object_id: this.objectId,
                    content: content
                });
                this.comments.unshift(response.data);
            } catch (error) {
                console.error(error);
            }
        },
        async replyToComment(parentId, content) {
            try {
                const response = await axios.post('/api/comments/', {
                    content_type: this.contentType,
                    object_id: this.objectId,
                    content: content,
                    parent: parentId
                });
                this.fetchComments();
            } catch (error) {
                console.error(error);
            }
        }
    }
};

// Usage:
// <CommentList content-type="blog.post" object-id="123" />
</script>
```

---

#### Option 2: Using Object-Specific Endpoint (Recommended)
```vue
<template>
    <div class="comments">
        <comment-form @submit="addComment" />
        
        <div v-if="loading">Loading...</div>
        
        <comment-item
            v-for="comment in comments"
            :key="comment.id"
            :comment="comment"
            @reply="replyToComment"
        />
    </div>
</template>

<script>
import axios from 'axios';

export default {
    name: 'CommentList',
    props: {
        appLabel: String,
        model: String,
        objectId: String
    },
    data() {
        return {
            comments: [],
            loading: true
        };
    },
    computed: {
        apiUrl() {
            return `/api/${this.appLabel}/${this.model}/${this.objectId}/comments/`;
        }
    },
    mounted() {
        this.fetchComments();
    },
    methods: {
        async fetchComments() {
            try {
                const response = await axios.get(this.apiUrl);
                this.comments = response.data.results;
            } catch (error) {
                console.error(error);
            } finally {
                this.loading = false;
            }
        },
        async addComment(content) {
            try {
                const response = await axios.post(this.apiUrl, {
                    content: content  // Only content!
                });
                this.comments.unshift(response.data);
            } catch (error) {
                console.error(error);
            }
        },
        async replyToComment(parentId, content) {
            try {
                const response = await axios.post(this.apiUrl, {
                    content: content,
                    parent: parentId
                });
                this.fetchComments();
            } catch (error) {
                console.error(error);
            }
        }
    }
};

// Usage:
// <CommentList app-label="blog" model="post" object-id="123" />
</script>
```

---

### Vanilla JavaScript

#### Option 1: Using Generic Endpoint
```javascript
class CommentSystem {
    constructor(contentType, objectId, apiUrl = '/api/comments/') {
        this.contentType = contentType;
        this.objectId = objectId;
        this.apiUrl = apiUrl;
        this.token = localStorage.getItem('authToken');
    }
    
    async fetchComments() {
        const url = new URL(this.apiUrl, window.location.origin);
        url.searchParams.append('content_type', this.contentType);
        url.searchParams.append('object_id', this.objectId);
        url.searchParams.append('ordering', '-created_at');
        
        const response = await fetch(url);
        const data = await response.json();
        return data.results;
    }
    
    async createComment(content, parentId = null) {
        const body = {
            content_type: this.contentType,
            object_id: this.objectId,
            content: content
        };
        
        if (parentId) {
            body.parent = parentId;
        }
        
        const response = await fetch(this.apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Token ${this.token}`
            },
            body: JSON.stringify(body)
        });
        
        if (!response.ok) {
            throw new Error('Failed to create comment');
        }
        
        return await response.json();
    }
    
    async flagComment(commentId, flag, reason) {
        const response = await fetch(
            `/api/comments/${commentId}/flag/`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Token ${this.token}`
                },
                body: JSON.stringify({ flag_type: flag, reason })
            }
        );
        
        return await response.json();
    }
}

// Usage:
// const comments = new CommentSystem('blog.post', '123');
// await comments.fetchComments();
// await comments.createComment('Great post!');
```

---

#### Option 2: Using Object-Specific Endpoint (Recommended)
```javascript
class CommentSystem {
    constructor(appLabel, model, objectId) {
        this.appLabel = appLabel;
        this.model = model;
        this.objectId = objectId;
        this.apiUrl = `/api/${appLabel}/${model}/${objectId}/comments/`;
        this.token = localStorage.getItem('authToken');
    }
    
    async fetchComments() {
        const url = new URL(this.apiUrl, window.location.origin);
        url.searchParams.append('ordering', '-created_at');
        
        const response = await fetch(url);
        const data = await response.json();
        return data.results;
    }
    
    async createComment(content, parentId = null) {
        const body = { content };
        
        if (parentId) {
            body.parent = parentId;
        }
        
        const response = await fetch(this.apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Token ${this.token}`
            },
            body: JSON.stringify(body)
        });
        
        if (!response.ok) {
            throw new Error('Failed to create comment');
        }
        
        return await response.json();
    }
    
    async flagComment(commentId, flag, reason) {
        const response = await fetch(
            `/api/comments/${commentId}/flag/`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Token ${this.token}`
                },
                body: JSON.stringify({ flag_type: flag, reason })
            }
        );
        
        return await response.json();
    }
}

// Usage:
// const comments = new CommentSystem('blog', 'post', '123');
// await comments.fetchComments();
// await comments.createComment('Great post!');
```

**Comparison:**

| Aspect | Generic Endpoint | Object-Specific Endpoint |
|--------|-----------------|-------------------------|
| Constructor params | `contentType, objectId` | `appLabel, model, objectId` |
| Security | Standard | Enhanced (zero-trust) |
| Request body | Includes metadata | Content only |
| URL complexity | Same for all operations | Object-specific |
| Best for | Admin tools | Public frontends |

---

## Real-World Examples

### Blog with Comments

```python
# models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Post(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title

# views.py
from django.views.generic import DetailView
from .models import Post
from django_comments.models import Comment

class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/post_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get comments for this post
        comments = Comment.objects.filter(
            content_type__app_label='blog',
            content_type__model='post',
            object_id=str(self.object.pk),
            is_public=True,
            parent__isnull=True  # Root comments only
        ).select_related('user').prefetch_related('children')
        
        context['comments'] = comments
        return context

# Template
{% extends 'base.html' %}
{% load comment_tags %}

{% block content %}
<article>
    <h1>{{ post.title }}</h1>
    <div class="post-meta">
        By {{ post.author.get_full_name }} on {{ post.created_at|date:"F j, Y" }}
    </div>
    <div class="post-content">
        {{ post.content|safe }}
    </div>
</article>

<section class="comments">
    <h2>
        Comments 
        ({% get_comment_count post %})
    </h2>
    
    {% if user.is_authenticated %}
        <form method="post" action="{% url 'api:comment-list' %}" class="comment-form">
            {% csrf_token %}
            <textarea name="content" required></textarea>
            <button type="submit">Post Comment</button>
        </form>
    {% else %}
        <p><a href="{% url 'login' %}">Log in</a> to comment.</p>
    {% endif %}
    
    {% get_root_comments post as root_comments %}
    {% for comment in root_comments %}
        {% include 'blog/comment_thread.html' %}
    {% endfor %}
</section>
{% endblock %}
```

### E-Commerce Product Reviews

```python
# settings.py
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['products.Product'],
    'MODERATOR_REQUIRED': True,  # Review all product reviews
    'MAX_COMMENT_LENGTH': 1000,
    'SPAM_DETECTION_ENABLED': True,
    'PROFANITY_FILTERING': True,
    'ALLOW_COMMENT_EDITING': True,
    'EDIT_TIME_WINDOW': 86400,  # 24 hours
}

# models.py
class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    @property
    def average_rating(self):
        """Calculate average rating from review comments."""
        from django_comments.models import Comment
        from django.db.models import Avg
        
        # Assuming reviews include rating in metadata
        reviews = Comment.objects.filter(
            content_type__app_label='products',
            content_type__model='product',
            object_id=str(self.pk),
            is_public=True
        )
        
        # You might store rating in a custom field
        # or parse it from comment content
        return 4.5  # Placeholder

# views.py
from django.views.generic import DetailView
from .models import Product

class ProductDetailView(DetailView):
    model = Product
    template_name = 'products/detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get verified purchase reviews
        reviews = Comment.objects.filter(
            content_type__app_label='products',
            content_type__model='product',
            object_id=str(self.object.pk),
            is_public=True
        ).select_related('user').order_by('-created_at')
        
        context['reviews'] = reviews
        context['review_count'] = reviews.count()
        context['average_rating'] = self.object.average_rating
        
        return context
```

---

**More questions?** Check the [API Reference](api_reference.md) for complete endpoint documentation.