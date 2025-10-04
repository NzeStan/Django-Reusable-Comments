# Configuration

Django Reusable Comments provides extensive configuration options to customize its behavior. All settings are specified in your Django settings file under the `DJANGO_COMMENTS_CONFIG` dictionary.

## Basic Configuration

Here's a basic configuration example:

```python
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['blog.Post', 'products.Product'],
    'USE_UUIDS': False,
    'MODERATOR_REQUIRED': False,
}
```

## Available Settings

Below is a comprehensive list of all available settings with their defaults and descriptions:

### Model Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `COMMENTABLE_MODELS` | `[]` | List of model paths that can be commented on (e.g., `'app.Model'`) |
| `USE_UUIDS` | `False` | Whether to use UUIDs for primary keys (False = integer PKs) |
| `COMMENT_MODEL` | `'django_comments.Comment'` | Path to the comment model to use (for custom models) |

### Moderation Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `MODERATOR_REQUIRED` | `False` | Whether moderation is required before comments are public |
| `AUTO_APPROVE_GROUPS` | `['Moderators', 'Staff']` | Auto-approve comments by users belonging to these groups |
| `CAN_VIEW_NON_PUBLIC_COMMENTS` | `['Moderators', 'Staff']` | Groups that can see non-public comments |
| `ALLOW_ANONYMOUS` | `True` | Whether to allow anonymous comments |

### Comment Structure

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_COMMENT_DEPTH` | `3` | Maximum comment depth for threaded comments (None = unlimited) |
| `MAX_COMMENT_LENGTH` | `3000` | Maximum allowed length for comment content |
| `COMMENT_FORMAT` | `'plain'` | Format for comment content ('plain', 'markdown', 'html') |

### Sorting and Pagination

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_SORT` | `'-created_at'` | Default sorting for comments |
| `ALLOWED_SORTS` | `['-created_at', 'created_at', '-updated_at', 'updated_at']` | Allowed sorting options |
| `PAGE_SIZE` | `20` | Default page size for paginated responses |

### Notifications

| Setting | Default | Description |
|---------|---------|-------------|
| `SEND_NOTIFICATIONS` | `False` | Whether to send email notifications for new comments |
| `NOTIFICATION_SUBJECT` | `'New comment on {object}'` | Subject template for notification emails |
| `NOTIFICATION_EMAIL_TEMPLATE` | `'django_comments/email/notification.txt'` | Email template for notifications |

### Spam and Content Filtering

| Setting | Default | Description |
|---------|---------|-------------|
| `SPAM_DETECTION_ENABLED` | `False` | Whether to enable spam detection |
| `SPAM_DETECTOR` | `None` | Custom spam detector function (path to importable function) |
| `SPAM_WORDS` | `[]` | List of words to flag as spam |
| `SPAM_ACTION` | `'flag'` | Action to take for spam ('flag', 'hide', or 'delete') |
| `PROFANITY_FILTERING` | `False` | Whether to enable profanity filtering |
| `PROFANITY_LIST` | `[]` | List of words to filter |
| `PROFANITY_ACTION` | `'censor'` | Action for profanity ('censor', 'flag', 'hide', or 'delete') |

### Cleanup and Logging

| Setting | Default | Description |
|---------|---------|-------------|
| `CLEANUP_AFTER_DAYS` | `None` | Days after which to remove non-public comments (None = never) |
| `LOGGER_NAME` | `'django_comments'` | Name of the logger to use |
| `API_RATE_LIMIT` | `'100/day'` | Rate limiting for API requests (DRF format) |

## Example Configurations

### Basic Blog Comments

```python
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['blog.Post'],
    'ALLOW_ANONYMOUS': True,
    'MAX_COMMENT_DEPTH': 2,
}
```

### Moderated Comments System

```python
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['forum.Topic', 'articles.Article'],
    'MODERATOR_REQUIRED': True,
    'ALLOW_ANONYMOUS': False,
    'SPAM_DETECTION_ENABLED': True,
    'SPAM_WORDS': ['viagra', 'casino', 'free money'],
    'CLEANUP_AFTER_DAYS': 30,  # Clean up non-public comments after 30 days
}
```

### Advanced E-commerce Reviews

```python
DJANGO_COMMENTS_CONFIG = {
    'COMMENTABLE_MODELS': ['products.Product'],
    'MODERATOR_REQUIRED': False,
    'AUTO_APPROVE_GROUPS': ['Verified Customers', 'Staff'],
    'ALLOW_ANONYMOUS': False,
    'PROFANITY_FILTERING': True,
    'PROFANITY_ACTION': 'censor',
    'SEND_NOTIFICATIONS': True,
    'NOTIFICATION_SUBJECT': 'New review on product {object}',
}
```

## Custom Comment Model

If you want to use a custom comment model, you can create your own model that inherits from `AbstractCommentBase`:

```python
# myapp/models.py
from django_comments.models import AbstractCommentBase

class CustomComment(AbstractCommentBase):
    # Your custom fields here
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    # ...
    
    class Meta:
        verbose_name = 'Custom Comment'
        verbose_name_plural = 'Custom Comments'
```

Then update your settings to use this model:

```python
DJANGO_COMMENTS_CONFIG = {
    # ...
    'COMMENT_MODEL': 'myapp.CustomComment',
    # ...
}
```

Make sure to create and run migrations for your custom model.