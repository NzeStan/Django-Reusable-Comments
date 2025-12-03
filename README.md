# Django Reusable Comments

A **production-grade**, reusable Django app for adding comment functionality to any model in your Django project. Built with performance optimization, extensive customization options, and full REST API support.

## ⚡ Performance Optimized

This package includes comprehensive performance optimizations:
- **Advanced query optimization** with `select_related` and `prefetch_related`
- **Intelligent caching system** with automatic invalidation
- **Batch operations** for comment counts across multiple objects
- **N+1 query prevention** throughout the codebase
- **Database indexes** for common query patterns

## Features

- ✅ **Model Agnostic** - Add comments to any Django model
- ✅ **ID Flexibility** - Support for both UUID and integer primary keys
- ✅ **Performance Optimized** - Advanced caching and query optimization
- ✅ **Highly Customizable** - Extensive settings and configuration options
- ✅ **Signals** - Robust signal system for extending functionality
- ✅ **Internationalization** - Full i18n support using gettext_lazy
- ✅ **DRF Integration** - Complete REST API via Django REST Framework
- ✅ **Template Tags** - Convenient template tags with caching support
- ✅ **Testing** - Comprehensive test suite (151 tests)
- ✅ **Documentation** - Thorough documentation for developers
- ✅ **Logging & Error Handling** - Sophisticated error handling
- ✅ **Admin Interface** - Feature-rich admin panel with optimized queries

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
    'rest_framework',  # Required for API
    'django_filters',  # Required for API filtering
    # ...
]
```

### 3. Configure your settings

```python
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['blog.Post', 'products.Product'],  # Models that can receive comments
    'USE_UUIDS': False,  # Use integer PKs (set to True for UUID)
    'MODERATOR_REQUIRED': False,  # Set to True to enable moderation workflow
    'MAX_COMMENT_DEPTH': 3,  # Maximum depth for threaded comments
    'ALLOW_ANONYMOUS': True,  # Allow anonymous comments
}
```

### 4. Run migrations

```bash
python manage.py migrate django_comments
```

**⚠️ IMPORTANT - UUID Migration Warning:**
If you're switching from integer PKs to UUIDs (or vice versa), migration `0004_alter_comment_id_alter_commentflag_id.py` changes the primary key type. This migration:
- **Requires a fresh database** (no existing comment data)
- **Is destructive** if run on a database with existing comments
- Should only be used during initial development or with a proper data migration strategy

For production databases, stick with your initial choice of USE_UUIDS setting.

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

## Usage

### REST API

#### Creating a comment

```python
# POST to /api/comments/
{
    "content_type": "blog.post",  
    "object_id": "123",
    "content": "This is a great post!",
    "parent": null  # Optional, for threaded comments
}
```

#### Listing comments for an object

```python
# GET /api/comments/?content_type=blog.post&object_id=123
```

#### Using the optimized endpoints

```python
# GET /api/content/blog.post/123/comments/
# Returns all comments for blog.post with ID 123 (fully optimized)
```

### Django Templates

Load the template tags and use the cache-optimized helpers:

```django
{% load comment_tags %}

<!-- Get comment count (uses cache) -->
<p>{% get_comment_count post %} comments</p>

<!-- Check if object has comments (uses cache) -->
{% if post|has_comments %}
    <a href="#comments">View Comments</a>
{% endif %}

<!-- Display comments (optimized query) -->
{% get_comments_for post as comments %}
{% for comment in comments %}
    <div class="comment">
        <strong>{{ comment.get_user_name }}</strong>
        <p>{{ comment.content }}</p>
    </div>
{% endfor %}

<!-- Display root comments with children (optimized for threading) -->
{% get_root_comments_for post as root_comments %}
{% for comment in root_comments %}
    <div class="comment">
        {{ comment.content }}
        {% for child in comment.children.all %}
            <div class="reply">{{ child.content }}</div>
        {% endfor %}
    </div>
{% endfor %}
```

### Using the Cache System (Python Code)

The cache system provides high-performance comment counting:

```python
from django_comments.cache import (
    get_comment_count_for_object,
    get_comment_counts_for_objects,
    warm_comment_cache_for_queryset,
)

# Get count for a single object (uses cache)
count = get_comment_count_for_object(post, public_only=True)

# Get counts for multiple objects efficiently (batch operation)
posts = Post.objects.all()[:20]
post_ids = [p.id for p in posts]
counts = get_comment_counts_for_objects(Post, post_ids, public_only=True)

# Pre-warm cache for better performance
posts = Post.objects.all()[:50]
warm_comment_cache_for_queryset(posts)
```

### Using in DRF Serializers

```python
from rest_framework import serializers
from django_comments.cache import get_comment_count_for_object

class PostSerializer(serializers.ModelSerializer):
    comment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = ['id', 'title', 'content', 'comment_count']
    
    def get_comment_count(self, obj):
        return get_comment_count_for_object(obj, public_only=True)
```

### Using Optimized Querysets

The package includes optimized queryset methods to prevent N+1 queries:

```python
from django_comments.models import Comment

# Get comments with all related data preloaded (no N+1 queries!)
comments = Comment.objects.for_model(post).optimized_for_list()

# For threaded display with full optimization
comments = Comment.objects.by_thread(thread_id).with_full_thread()

# Get public comments only (common pattern, optimized)
comments = Comment.objects.for_model(post).public()

# Search comments (optimized)
comments = Comment.objects.search("django").with_user_and_content_type()
```

### Using Signals

```python
from django.dispatch import receiver
from django_comments.signals import comment_post_save, comment_flagged

@receiver(comment_post_save)
def handle_new_comment(sender, comment, created, **kwargs):
    if created:
        # Send notification, update counters, etc.
        pass

@receiver(comment_flagged)
def handle_flagged_comment(sender, flag, comment, user, **kwargs):
    # Handle flagged content
    pass
```

### Management Commands

#### Clean up old comments

```bash
# Remove comments older than 30 days
python manage.py cleanup_comments --days 30

# Remove spam comments
python manage.py cleanup_comments --remove-spam

# Dry run to see what would be deleted
python manage.py cleanup_comments --days 30 --dry-run
```

## Configuration Options

All configuration is done via `DJANGO_COMMENTS_CONFIG` in your settings:

```python
DJANGO_COMMENTS_CONFIG = {
    # =========================================================================
    # CORE SETTINGS (Actively Used)
    # =========================================================================
    
    # Models that can receive comments
    'COMMENTABLE_MODELS': ['blog.Post', 'products.Product'],
    
    # Primary key type
    'USE_UUIDS': False,  # False = integers, True = UUIDs
    
    # Moderation
    'MODERATOR_REQUIRED': False,  # Require approval before comments are public
    'AUTO_APPROVE_GROUPS': ['Moderators', 'Staff'],  # Auto-approve for these groups
    'CAN_VIEW_NON_PUBLIC_COMMENTS': ['Moderators', 'Staff'],  # Who can see hidden comments
    
    # Threading
    'MAX_COMMENT_DEPTH': 3,  # Maximum nesting level (None = unlimited)
    
    # Content
    'MAX_COMMENT_LENGTH': 3000,  # Maximum characters
    
    # Anonymous comments
    'ALLOW_ANONYMOUS': True,
    
    # Sorting
    'DEFAULT_SORT': '-created_at',
    
    # Cleanup
    'CLEANUP_AFTER_DAYS': None,  # Auto-remove old non-public comments
    
    # Spam detection
    'SPAM_DETECTION_ENABLED': False,
    'SPAM_WORDS': [],  # List of words to flag as spam
    
    # Profanity filtering
    'PROFANITY_FILTERING': False,
    'PROFANITY_LIST': [],  # List of words to censor
    'PROFANITY_ACTION': 'censor',  # 'censor', 'flag', 'hide', or 'delete'
    
    # Caching
    'CACHE_TIMEOUT': 3600,  # Cache timeout in seconds (default: 1 hour)
    
    # Logging
    'LOGGER_NAME': 'django_comments',
}
```

## Performance Features

### Automatic Cache Invalidation

The cache system automatically invalidates when comments are created, updated, or deleted:

```python
# Creating a comment automatically invalidates cache
comment = Comment.objects.create(
    content_type=content_type,
    object_id=post.id,
    content="New comment"
)
# Cache for this post is now invalidated automatically

# Next call will recalculate and cache
count = get_comment_count_for_object(post)  # Fresh data
```

### Optimized Admin Interface

The admin interface uses optimized queries to prevent N+1 problems:

- User information (select_related)
- Content type (select_related)
- Parent comments (select_related)
- Flags (prefetch_related)
- Children count (annotated)

### Database Indexes

The package includes optimized database indexes for common query patterns:

- Compound index on `(content_type, object_id)` for object lookups
- Index on `created_at` for sorting
- Compound index on `(is_public, is_removed, created_at)` for public comments
- Index on `thread_id` for threaded queries
- Index on `user` for user-specific queries

## API Endpoints

### Comments

- `GET /api/comments/` - List all comments (paginated, filterable)
- `POST /api/comments/` - Create a new comment
- `GET /api/comments/{id}/` - Get a specific comment
- `PATCH /api/comments/{id}/` - Update a comment (owner only)
- `DELETE /api/comments/{id}/` - Delete a comment (owner only)

### Filtering

```python
# Filter by content type and object
GET /api/comments/?content_type=blog.post&object_id=123

# Filter by user
GET /api/comments/?user=5

# Filter by date range
GET /api/comments/?created_after=2024-01-01&created_before=2024-12-31

# Filter by status
GET /api/comments/?is_public=true

# Search
GET /api/comments/?search=django

# Ordering
GET /api/comments/?ordering=-created_at
```

### Moderation

- `POST /api/comments/{id}/flag/` - Flag a comment (authenticated users)
- `POST /api/comments/{id}/approve/` - Approve a comment (moderators only)
- `POST /api/comments/{id}/reject/` - Reject a comment (moderators only)

### Content-Specific Comments

```python
# Get all comments for a specific object (optimized endpoint)
GET /api/content/{content_type}/{object_id}/comments/

# Example:
GET /api/content/blog.post/123/comments/
```

## Advanced Usage

### Custom Comment Model

You can extend the comment model:

```python
# myapp/models.py
from django_comments.models import Comment

class CustomComment(Comment):
    rating = models.IntegerField(default=0)
    
    class Meta:
        proxy = True  # Or set to False for separate table

# settings.py
# Note: Custom models are not yet fully supported
# Stick with the built-in Comment or UUIDComment models
```

### Celery Integration

```python
from celery import shared_task
from django_comments.cache import warm_comment_cache_for_queryset

@shared_task
def warm_homepage_cache():
    """Pre-warm cache for homepage posts."""
    featured_posts = Post.objects.filter(featured=True)[:10]
    warm_comment_cache_for_queryset(featured_posts)
```

### GraphQL Integration

```python
import graphene
from django_comments.cache import get_comment_count_for_object

class PostType(DjangoObjectType):
    comment_count = graphene.Int()
    
    class Meta:
        model = Post
    
    def resolve_comment_count(self, info):
        return get_comment_count_for_object(self, public_only=True)
```

## Testing

Run the test suite:

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=django_comments

# Run specific test file
pytest django_comments/tests/test_api.py

# Run with verbose output
pytest -v
```

## Requirements

- Python >= 3.8
- Django >= 3.2
- djangorestframework >= 3.12.0
- django-filter >= 21.1

## Contributing

Contributions are welcome! Please check out our [Contributing Guide](CONTRIBUTING.md).

## Performance Benchmarks

On a typical blog with 1000 posts and 10,000 comments:

**Without optimization:**
- List 20 posts with comment counts: ~500ms (200+ queries)
- Display post with comments: ~300ms (50+ queries)

**With optimization:**
- List 20 posts with comment counts: ~50ms (2-3 queries, or 0 with warm cache)
- Display post with comments: ~30ms (1-2 queries)

**Cache hit rates:** Typically 95%+ in production with proper cache warming

## Known Limitations

1. **UUID Migration**: Switching between integer and UUID primary keys requires a fresh database
2. **Spam Detection**: Currently validates content but doesn't automatically hide/delete spam
3. **Email Notifications**: Not yet implemented (planned for future release)
4. **Rate Limiting**: Use Django REST Framework's throttling instead

## Future Features (Coming Soon)

- Email notifications for new comments
- Markdown/HTML comment formatting
- Advanced spam detection with ML
- Real-time comment updates via WebSockets
- Comment reactions (likes, upvotes, etc.)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/NzeStan/django-reusable-comments/issues)
- **Discussions**: [GitHub Discussions](https://github.com/NzeStan/django-reusable-comments/discussions)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

## Credits

Developed and maintained by Ifeanyi Stanley Nnamani.

Special thanks to all contributors who have helped improve this package!