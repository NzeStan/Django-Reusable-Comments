from django.conf import settings
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _

# Default settings that can be overridden by Django settings
DEFAULTS = {
    # List of model paths that can be commented on
    'COMMENTABLE_MODELS': [],
    
    # Whether to use UUIDs for primary keys (False = integer PKs)
    'USE_UUIDS': False,
    
    # Whether moderation is required before comments are public
    'MODERATOR_REQUIRED': False,
    
    # Maximum comment depth for threaded comments (None = unlimited)
    'MAX_COMMENT_DEPTH': 3,
    
    # Maximum allowed length for comment content
    'MAX_COMMENT_LENGTH': 3000,
    
    # Auto-approve comments by users belonging to these groups
    'AUTO_APPROVE_GROUPS': ['Moderators', 'Staff'],
    
    # Who can see non-public comments
    'CAN_VIEW_NON_PUBLIC_COMMENTS': ['Moderators', 'Staff'],
    
    # Allow anonymous comments
    'ALLOW_ANONYMOUS': True,
    
    # Comment content format (plain, markdown, html)
    'COMMENT_FORMAT': 'plain',
    
    # Custom comment model
    'COMMENT_MODEL': 'django_comments.Comment',
    
    # Comment sorting options
    'DEFAULT_SORT': '-created_at',
    'ALLOWED_SORTS': [
        '-created_at',
        'created_at',
        '-updated_at',
        'updated_at',
    ],
    
    # Pagination settings
    'PAGE_SIZE': 20, #
    
    # Email notification settings
    'SEND_NOTIFICATIONS': False,
    'NOTIFICATION_SUBJECT': _('New comment on {object}'),
    'NOTIFICATION_EMAIL_TEMPLATE': 'django_comments/email/notification.txt',
    
    # Spam detection settings
    'SPAM_DETECTION_ENABLED': False,
    'SPAM_DETECTOR': None,
    'SPAM_WORDS': [],
    'SPAM_ACTION': 'flag',  # 'flag', 'hide', or 'delete'
    
    # Comment cleanup settings
    'CLEANUP_AFTER_DAYS': None,  # Days after which to remove non-public comments
    
    # Logger name
    'LOGGER_NAME': 'django_comments',
    
    # API rate limiting
    'API_RATE_LIMIT': '100/day',
    
    # Extended profanity filtering
    'PROFANITY_FILTERING': False,
    'PROFANITY_LIST': [],
    'PROFANITY_ACTION': 'censor',  # 'censor', 'flag', 'hide', or 'delete'
}


class CommentsSettings:
    """
    A settings object for django-comments that handles default vs user settings.
    """
    
    def __init__(self, user_settings=None, defaults=None):
        self.user_settings = user_settings or {}
        self.defaults = defaults or DEFAULTS
        
    def __getattr__(self, attr):
        if attr not in self.defaults:
            raise AttributeError(f"Invalid django-comments setting: '{attr}'")
        
        # Get the setting from user settings or use the default
        value = self.user_settings.get(attr, self.defaults[attr])
        
        # Convert model paths to content types if needed
        if attr == 'COMMENTABLE_MODELS':
            # Will be processed by utils.get_commentable_models() when needed
            return value
        
        return value
        
    @property
    def as_dict(self):
        """
        Return all settings as a dictionary.
        """
        settings_dict = {}
        for key in self.defaults.keys():
            settings_dict[key] = getattr(self, key)
        return settings_dict


# Load user settings from Django settings
USER_SETTINGS = getattr(settings, 'DJANGO_COMMENTS_CONFIG', {})

# Create the settings object
comments_settings = CommentsSettings(USER_SETTINGS, DEFAULTS)