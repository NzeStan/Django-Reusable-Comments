from django.conf import settings
from django.utils.translation import gettext_lazy as _
import warnings
from django.core.exceptions import ImproperlyConfigured

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
    
    # Comment format ('plain', 'markdown', 'html')
    # - 'plain': Plain text with HTML escaped (safest)
    # - 'markdown': Markdown syntax supported (requires markdown package)
    # - 'html': HTML allowed with sanitization (requires bleach package)
    'COMMENT_FORMAT': 'plain',
    
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
    # API PAGINATION
    # ============================================================================
    
    # Number of comments per page (integrates with DRF pagination)
    'PAGE_SIZE': 20,
    
    # Allow client to specify page size via query parameter
    'PAGE_SIZE_QUERY_PARAM': 'page_size',
    
    # Maximum page size that can be requested
    'MAX_PAGE_SIZE': 100,
    
    # ============================================================================
    # API RATE LIMITING (integrates with DRF throttling)
    # ============================================================================
    
    # Rate limit for authenticated users
    # Format: 'number/period' (e.g., '100/day', '10/hour', '5/minute')
    'API_RATE_LIMIT': '100/day',
    
    # Rate limit for anonymous users (typically lower)
    'API_RATE_LIMIT_ANON': '20/day',
    
    # Burst rate limit (short-term limit to prevent rapid spam)
    'API_RATE_LIMIT_BURST': '5/min',
    
    # ============================================================================
    # NOTIFICATIONS
    # ============================================================================
    
    # Enable email notifications
    'SEND_NOTIFICATIONS': False,
    
    # Email subject template (can use {object} placeholder)
    'NOTIFICATION_SUBJECT': _('New comment on {object}'),
    
    # Email templates for different notification types
    'NOTIFICATION_EMAIL_TEMPLATE': 'django_comments/email/new_comment.html',
    'NOTIFICATION_REPLY_TEMPLATE': 'django_comments/email/comment_reply.html',
    'NOTIFICATION_APPROVED_TEMPLATE': 'django_comments/email/comment_approved.html',
    'NOTIFICATION_REJECTED_TEMPLATE': 'django_comments/email/comment_rejected.html',
    'NOTIFICATION_MODERATOR_TEMPLATE': 'django_comments/email/moderator_notification.html',
    
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
    
    # Custom spam detector function (optional)
    # Should be a callable that takes content string and returns (is_spam: bool, reason: str)
    # Example: 'myapp.spam.detect_spam'
    'SPAM_DETECTOR': None,
    
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
    
    # ============================================================================
    # DEPRECATED SETTINGS (for backward compatibility)
    # ============================================================================
    
    # DEPRECATED: Use DJANGO_COMMENTS_COMMENT_MODEL setting instead
    # This setting is kept for backward compatibility but will be removed in 1.0
    'COMMENT_MODEL': None,

    # ============================================================================
    # FLAG THRESHOLDS & AUTO-MODERATION
    # ============================================================================
    
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
    
    # ============================================================================
    # TRUSTED USERS & AUTO-APPROVAL
    # ============================================================================
    
    # Auto-approve users after N approved comments (None = disabled)
    'AUTO_APPROVE_AFTER_N_APPROVED': 5,
    
    # User groups that bypass moderation
    'TRUSTED_USER_GROUPS': ['Verified', 'Premium'],
    
    # ============================================================================
    # FLAG ABUSE PREVENTION
    # ============================================================================
    
    # Maximum flags a user can create per day
    'MAX_FLAGS_PER_DAY': 20,
    
    # Maximum flags a user can create per hour
    'MAX_FLAGS_PER_HOUR': 5,
    
    # ============================================================================
    # ENHANCED NOTIFICATIONS
    # ============================================================================
    
    # Notify moderators when comment is flagged
    'NOTIFY_ON_FLAG': True,
    
    # Notify moderators when comment is auto-hidden
    'NOTIFY_ON_AUTO_HIDE': True,
    
    # Email template for flag notifications
    'NOTIFICATION_FLAG_TEMPLATE': 'django_comments/email/moderator_flag_notification.html',
    
    # ============================================================================
    # COMMENT EDITING
    # ============================================================================
    
    # Enable comment editing
    'ALLOW_COMMENT_EDITING': True,
    
    # Time window for editing (in seconds, None = unlimited)
    'EDIT_TIME_WINDOW': 3600,  # 1 hour
    
    # Track edit history
    'TRACK_EDIT_HISTORY': True,
    
    # ============================================================================
    # MODERATION QUEUE
    # ============================================================================
    
    # Page size for moderation queue
    'MODERATION_QUEUE_PAGE_SIZE': 50,
    
    # Days to keep moderation logs
    'MODERATION_LOG_RETENTION_DAYS': 90,
    
    # ============================================================================
    # BAN SYSTEM
    # ============================================================================
    
    # Default ban duration in days (None = permanent)
    'DEFAULT_BAN_DURATION_DAYS': 30,
    
    # Auto-ban after N rejected comments
    'AUTO_BAN_AFTER_REJECTIONS': 5,
    
    # Auto-ban after N spam flags
    'AUTO_BAN_AFTER_SPAM_FLAGS': 3,
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
        self._spam_detector_cache = None
        
        # Handle deprecated COMMENT_MODEL setting
        self._handle_deprecated_settings()
        
    def _handle_deprecated_settings(self):
        """Handle deprecated settings with warnings."""
        if 'COMMENT_MODEL' in self.user_settings and self.user_settings['COMMENT_MODEL']:
            warnings.warn(
                "DJANGO_COMMENTS_CONFIG['COMMENT_MODEL'] is deprecated. "
                "Use DJANGO_COMMENTS_COMMENT_MODEL setting instead. "
                "This will be removed in version 1.0.",
                DeprecationWarning,
                stacklevel=2
            )
            # Set the new setting if not already set
            if not hasattr(settings, 'DJANGO_COMMENTS_COMMENT_MODEL'):
                settings.DJANGO_COMMENTS_COMMENT_MODEL = self.user_settings['COMMENT_MODEL']
        
    def __getattr__(self, attr):
        if attr not in self.defaults:
            raise AttributeError(f"Invalid django-comments setting: '{attr}'")
        
        # Get the setting from user settings or use the default
        value = self.user_settings.get(attr, self.defaults[attr])
        
        # Special handling for SPAM_DETECTOR
        if attr == 'SPAM_DETECTOR' and value:
            return self._get_spam_detector(value)
        
        # Convert model paths to content types if needed
        if attr == 'COMMENTABLE_MODELS':
            # Will be processed by utils.get_commentable_models() when needed
            return value
        
        return value
    
    def _get_spam_detector(self, detector_path):
        """
        Load and cache spam detector function.
        
        Args:
            detector_path: Dotted path to spam detector function
        
        Returns:
            Callable spam detector function
        """
        if self._spam_detector_cache is not None:
            return self._spam_detector_cache
        
        if callable(detector_path):
            self._spam_detector_cache = detector_path
            return detector_path
        
        # Import from string path
        try:
            from django.utils.module_loading import import_string
            detector = import_string(detector_path)
            
            if not callable(detector):
                raise TypeError(
                    f"SPAM_DETECTOR must be callable, got {type(detector)}"
                )
            
            self._spam_detector_cache = detector
            return detector
            
        except ImportError as e:
            raise ImproperlyConfigured(
                f"Could not import spam detector '{detector_path}': {e}"
            )
        except Exception as e:
            raise ImproperlyConfigured(
                f"Error loading spam detector '{detector_path}': {e}"
            )
        
    @property
    def as_dict(self):
        """
        Return all settings as a dictionary.
        """
        settings_dict = {}
        for key in self.defaults.keys():
            settings_dict[key] = getattr(self, key)
        return settings_dict
    
    def validate(self):
        """
        Validate settings for common configuration errors.
        Raises ImproperlyConfigured for invalid settings.
        """
        errors = []
        
        # Validate COMMENT_FORMAT
        valid_formats = ['plain', 'markdown', 'html']
        if self.COMMENT_FORMAT not in valid_formats:
            errors.append(
                f"COMMENT_FORMAT must be one of {valid_formats}, "
                f"got '{self.COMMENT_FORMAT}'"
            )
        
        # Validate SPAM_ACTION
        valid_spam_actions = ['flag', 'hide', 'delete']
        if self.SPAM_ACTION not in valid_spam_actions:
            errors.append(
                f"SPAM_ACTION must be one of {valid_spam_actions}, "
                f"got '{self.SPAM_ACTION}'"
            )
        
        # Validate PROFANITY_ACTION
        valid_profanity_actions = ['censor', 'flag', 'hide', 'delete']
        if self.PROFANITY_ACTION not in valid_profanity_actions:
            errors.append(
                f"PROFANITY_ACTION must be one of {valid_profanity_actions}, "
                f"got '{self.PROFANITY_ACTION}'"
            )
        
        # Validate pagination settings
        if self.PAGE_SIZE and self.PAGE_SIZE <= 0:
            errors.append(f"PAGE_SIZE must be positive, got {self.PAGE_SIZE}")
        
        if self.MAX_PAGE_SIZE and self.MAX_PAGE_SIZE < self.PAGE_SIZE:
            errors.append(
                f"MAX_PAGE_SIZE ({self.MAX_PAGE_SIZE}) must be >= "
                f"PAGE_SIZE ({self.PAGE_SIZE})"
            )
        
        # Validate notification templates if notifications enabled
        if self.SEND_NOTIFICATIONS:
            required_templates = [
                'NOTIFICATION_EMAIL_TEMPLATE',
                'NOTIFICATION_REPLY_TEMPLATE',
                'NOTIFICATION_APPROVED_TEMPLATE',
                'NOTIFICATION_REJECTED_TEMPLATE',
                'NOTIFICATION_MODERATOR_TEMPLATE',
            ]
            for template_setting in required_templates:
                if not getattr(self, template_setting):
                    errors.append(
                        f"{template_setting} must be set when SEND_NOTIFICATIONS is True"
                    )
        
        if errors:
            from django.core.exceptions import ImproperlyConfigured
            raise ImproperlyConfigured(
                "Invalid django-comments configuration:\n" +
                "\n".join(f"  - {error}" for error in errors)
            )


# Load user settings from Django settings
USER_SETTINGS = getattr(settings, 'DJANGO_COMMENTS_CONFIG', {})

# Create the settings object
comments_settings = CommentsSettings(USER_SETTINGS, DEFAULTS)