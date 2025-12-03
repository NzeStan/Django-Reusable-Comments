from django.conf import settings

# Default settings that can be overridden by Django settings
DEFAULTS = {
    # ============================================================================
    # MODEL CONFIGURATION
    # ============================================================================
    
    # List of model paths that can be commented on
    # Format: ['app_label.ModelName', 'another_app.AnotherModel']
    'COMMENTABLE_MODELS': [],
    
    # Whether to use UUIDs for primary keys (False = integer PKs, True = UUID PKs)
    # WARNING: Changing this on existing database will break everything
    'USE_UUIDS': False,
    
    # ============================================================================
    # MODERATION SETTINGS
    # ============================================================================
    
    # Whether moderation is required before comments are public
    # If True, all new comments will have is_public=False until approved
    'MODERATOR_REQUIRED': False,
    
    # Auto-approve comments by users belonging to these groups
    # Users in these groups bypass MODERATOR_REQUIRED
    'AUTO_APPROVE_GROUPS': ['Moderators', 'Staff'],
    
    # Who can see non-public comments
    # Users in these groups can view comments with is_public=False
    'CAN_VIEW_NON_PUBLIC_COMMENTS': ['Moderators', 'Staff'],
    
    # ============================================================================
    # THREADING SETTINGS
    # ============================================================================
    
    # Maximum comment depth for threaded comments (None = unlimited)
    # Set to an integer to limit reply depth (e.g., 3 for up to 3 levels)
    'MAX_COMMENT_DEPTH': 3,
    
    # ============================================================================
    # CONTENT SETTINGS
    # ============================================================================
    
    # Maximum allowed length for comment content (in characters)
    'MAX_COMMENT_LENGTH': 3000,
    
    # Allow anonymous comments
    # If True, unauthenticated users can post comments with email/name
    # If False, only authenticated users can comment
    'ALLOW_ANONYMOUS': True,
    
    # ============================================================================
    # SORTING & DISPLAY
    # ============================================================================
    
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
    
    # ============================================================================
    # CLEANUP SETTINGS
    # ============================================================================
    
    # Days after which to remove non-public comments (None = never cleanup)
    # Used by the cleanup_comments management command
    'CLEANUP_AFTER_DAYS': None,
    
    # ============================================================================
    # LOGGING
    # ============================================================================
    
    # Logger name for django-comments
    'LOGGER_NAME': 'django_comments',
    
    # ============================================================================
    # SPAM DETECTION
    # ============================================================================
    
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
    
    # ============================================================================
    # PROFANITY FILTERING
    # ============================================================================
    
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
    
    # ============================================================================
    # CACHING
    # ============================================================================
    
    # Cache timeout in seconds (default: 1 hour)
    # Used by the built-in caching system for comment counts
    'CACHE_TIMEOUT': 3600,
}


class CommentsSettings:
    """
    A settings object for django-comments that handles default vs user settings.
    
    Usage:
        from django_comments.conf import comments_settings
        
        # Access settings
        max_length = comments_settings.MAX_COMMENT_LENGTH
        
        # Get all settings as dict
        all_settings = comments_settings.as_dict
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