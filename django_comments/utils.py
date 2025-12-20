import re
import logging
import importlib
from datetime import timedelta
from functools import lru_cache
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Type, Union
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.db import IntegrityError, models, transaction
from django.db.models import Count
from django.utils import timezone
from django_comments.conf import comments_settings
from django_comments.models import CommentFlag
from .models import BannedUser

User = get_user_model()

logger = logging.getLogger(comments_settings.LOGGER_NAME)

    

def get_comment_model():
    """
    Return the Comment model.
    
    
    Returns:
        Comment model class
    """
    try:
        return apps.get_model('django_comments', 'Comment', require_ready=False)
    except (ValueError, LookupError) as e:
        raise ImproperlyConfigured(
            f"Could not load comment model 'django_comments.Comment': {e}"
        ) from e


@lru_cache(maxsize=1)
def get_commentable_models() -> List[Type[models.Model]]:
    """Return a list of model classes that can be commented on."""
    model_paths = comments_settings.COMMENTABLE_MODELS

    if not model_paths:
        logger.warning("No commentable models defined in settings.")
        return []

    models_list = []
    for model_path in model_paths:
        model = None
        
        # Strategy 1: Try app_label.ModelName (case-insensitive)
        try:
            model = apps.get_model(model_path)
            if model:
                models_list.append(model)
                logger.debug(f"Loaded model '{model_path}' via apps.get_model")
                continue
        except (ValueError, LookupError) as e:
            logger.debug(f"apps.get_model failed for '{model_path}': {e}")
        
        # Strategy 2: Try with different case variations
        if '.' in model_path:
            app_label, model_name = model_path.split('.', 1)
            try:
                model = apps.get_model(app_label, model_name.lower())
                if model:
                    models_list.append(model)
                    logger.debug(f"Loaded model '{model_path}' with lowercase")
                    continue
            except (ValueError, LookupError):
                pass
            
            try:
                model = apps.get_model(app_label, model_name)
                if model:
                    models_list.append(model)
                    logger.debug(f"Loaded model '{model_path}' with original case")
                    continue
            except (ValueError, LookupError):
                pass

        # Strategy 3: Try module.path.ModelClass format
        try:
            if model_path.count('.') >= 2:
                module_path, class_name = model_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
                model = getattr(module, class_name)
                if model and issubclass(model, models.Model):
                    models_list.append(model)
                    logger.debug(f"Loaded model '{model_path}' via import")
                    continue
        except (ImportError, AttributeError, ValueError, TypeError):
            pass
        
        logger.error(f"Could not load model '{model_path}'")

    if not models_list:
        logger.warning(f"No models could be loaded from COMMENTABLE_MODELS: {model_paths}")
    else:
        logger.info(f"Successfully loaded {len(models_list)} commentable models")

    return models_list


def get_commentable_content_types() -> List[ContentType]:
    """Return a list of content types for commentable models."""
    models_list = get_commentable_models()
    return [ContentType.objects.get_for_model(model) for model in models_list]


def get_model_from_content_type_string(content_type_str: str) -> Optional[Type[models.Model]]:
    """
    Convert a string like 'app_label.ModelName' to a model class.
    Handles case-insensitive model names since Django's ContentType uses lowercase.
    """
    try:
        # Try as-is first
        return apps.get_model(content_type_str)
    except (ValueError, LookupError):
        # Try with lowercase model name
        if '.' in content_type_str:
            app_label, model_name = content_type_str.split('.', 1)
            try:
                return apps.get_model(app_label, model_name.lower())
            except (ValueError, LookupError):
                pass
        
        logger.error(f"Invalid content type string: {content_type_str}")
        return None


def get_object_from_content_type_and_id(content_type_str: str, obj_id: Union[str, int]) -> Optional[models.Model]:
    """Get a model instance from a content type string and object ID."""
    model = get_model_from_content_type_string(content_type_str)
    if not model:
        return None

    try:
        return model.objects.get(pk=obj_id)
    except ObjectDoesNotExist:
        logger.error(f"Object with ID {obj_id} not found for model {content_type_str}")
        return None


def check_content_for_spam(content: str) -> Tuple[bool, Optional[str]]:
    """
    Check if content contains spam.
    
    Returns:
        Tuple of (is_spam: bool, reason: Optional[str])
    """
    if not comments_settings.SPAM_DETECTION_ENABLED:
        return False, None
    
    # Try custom spam detector first
    custom_detector = comments_settings.SPAM_DETECTOR
    if custom_detector:
        try:
            result = custom_detector(content)
            # Handle different return formats
            if isinstance(result, tuple):
                is_spam, reason = result
                if is_spam:
                    logger.info(f"Custom spam detector flagged content: {reason}")
                return is_spam, reason
            elif isinstance(result, bool):
                if result:
                    logger.info("Custom spam detector flagged content")
                return result, "Detected by custom spam detector" if result else None
        except Exception as e:
            logger.error(f"Custom spam detector failed: {e}")
            # Fall through to default detection
    
    # Default spam word detection
    if not comments_settings.SPAM_WORDS:
        return False, None
    
    content_lower = content.lower()
    for word in comments_settings.SPAM_WORDS:
        if word.lower() in content_lower:
            logger.info(f"Spam detected: content contains '{word}'")
            return True, f"Contains spam keyword: {word}"
    
    return False, None


def check_content_for_profanity(content: str) -> bool:
    """
    Check if content contains profanity.
    
    Returns:
        True if profanity detected, False otherwise
    """
    if not comments_settings.PROFANITY_FILTERING or not comments_settings.PROFANITY_LIST:
        return False
    
    content_lower = content.lower()
    for word in comments_settings.PROFANITY_LIST:
        # Use word boundary to match whole words only
        pattern = r'\b' + re.escape(word.lower()) + r'\b'
        if re.search(pattern, content_lower):
            logger.info(f"Profanity detected: content contains '{word}'")
            return True
    
    return False


def filter_profanity(content: str) -> str:
    """
    Filter profanity from comment content by replacing words with asterisks.
    Only censors if PROFANITY_ACTION is 'censor'.
    """
    if (not comments_settings.PROFANITY_FILTERING or
        not comments_settings.PROFANITY_LIST or
        comments_settings.PROFANITY_ACTION != 'censor'):
        return content

    result = content
    for word in comments_settings.PROFANITY_LIST:
        pattern = r'\b' + re.escape(word) + r'\b'
        replacement = '*' * len(word)
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result


def is_comment_content_allowed(content: str) -> tuple[bool, Optional[str]]:
    """
    FIXED: Check if comment content is allowed (not spam, not profane, etc.)
    
    NEW BEHAVIOR:
    - 'flag' action → Allow creation (True)
    - 'hide' action → Allow creation (True) - will be hidden in create()
    - 'delete' action → Reject creation (False)
    
    Returns:
        tuple: (is_allowed: bool, reason: Optional[str])
               reason is only provided if content is not allowed
    """
    if not content or len(content) > comments_settings.MAX_COMMENT_LENGTH:
        return False, "Content is empty or exceeds maximum length"

    # Check for spam
    if comments_settings.SPAM_DETECTION_ENABLED:
        is_spam, spam_reason = check_content_for_spam(content)
        if is_spam:
            action = comments_settings.SPAM_ACTION
            if action == 'delete':  # CHANGED: Only 'delete' rejects
                return False, f"Content flagged as spam: {spam_reason}"
            # If action is 'flag' or 'hide', we allow it (will be handled in create())

    # Check for profanity
    if comments_settings.PROFANITY_FILTERING:
        has_profanity = check_content_for_profanity(content)
        if has_profanity:
            action = comments_settings.PROFANITY_ACTION
            if action == 'delete':  # CHANGED: Only 'delete' rejects
                return False, "Content contains profanity"
            # If action is 'censor', 'flag', or 'hide', we allow it

    return True, None



def process_comment_content(content: str) -> tuple[str, dict]:
    """
    FIXED: Process comment content for spam and profanity.
    
    This is called during comment creation to:
    1. Filter profanity (if action is 'censor')
    2. Determine flags to apply (if action is 'flag')
    3. Determine if should hide (if action is 'hide') ← NEW
    
    NEW: Returns 'should_hide' and 'hide_reason' metadata for 'hide' actions.
    
    Returns:
        tuple: (processed_content: str, flags_to_apply: dict)
               flags_to_apply contains metadata about detected issues
               
    flags_to_apply keys:
        - is_spam: bool
        - has_profanity: bool
        - auto_flag_spam: bool
        - auto_flag_profanity: bool
        - spam_reason: str
        - should_hide: bool (NEW)
        - hide_reason: str (NEW)
    """
    
    processed_content = content
    flags_to_apply = {
        'is_spam': False,
        'has_profanity': False,
        'auto_flag_spam': False,
        'auto_flag_profanity': False,
        'spam_reason': None,
        'should_hide': False,  # NEW
        'hide_reason': None,   # NEW
    }
    
    # =========================================================================
    # Check spam
    # =========================================================================
    if comments_settings.SPAM_DETECTION_ENABLED:
        is_spam, spam_reason = check_content_for_spam(content)
        if is_spam:
            flags_to_apply['is_spam'] = True
            flags_to_apply['spam_reason'] = spam_reason
            
            action = comments_settings.SPAM_ACTION
            if action == 'flag':
                flags_to_apply['auto_flag_spam'] = True
                logger.info(f"Content will be auto-flagged as spam: {spam_reason}")
            elif action == 'hide':  # NEW
                flags_to_apply['should_hide'] = True
                flags_to_apply['hide_reason'] = f"Auto-hidden: spam detected - {spam_reason}"
                flags_to_apply['auto_flag_spam'] = True  # Also flag it
                logger.info(f"Content will be hidden: {spam_reason}")
            # 'delete' action is handled by is_comment_content_allowed()
    
    # =========================================================================
    # Check and process profanity
    # =========================================================================
    if comments_settings.PROFANITY_FILTERING:
        has_profanity = check_content_for_profanity(content)
        if has_profanity:
            flags_to_apply['has_profanity'] = True
            
            action = comments_settings.PROFANITY_ACTION
            if action == 'censor':
                processed_content = filter_profanity(content)
                logger.info("Profanity censored in content")
            elif action == 'flag':
                flags_to_apply['auto_flag_profanity'] = True
                logger.info("Content will be auto-flagged for profanity")
            elif action == 'hide':  # NEW
                flags_to_apply['should_hide'] = True
                # Don't overwrite spam reason if already set
                if not flags_to_apply['hide_reason']:
                    flags_to_apply['hide_reason'] = "Auto-hidden: profanity detected"
                else:
                    flags_to_apply['hide_reason'] += " and profanity detected"
                flags_to_apply['auto_flag_profanity'] = True  # Also flag it
                logger.info("Content will be hidden due to profanity")
            # 'delete' action is handled by is_comment_content_allowed()
    
    return processed_content, flags_to_apply


def apply_automatic_flags(comment):
    """
    FIXED: Apply automatic flags to a comment based on content analysis.
    
    Replace your apply_automatic_flags() function in utils.py with this complete function.
    
    Args:
        comment: Comment instance to potentially flag
    
    This function is called after a comment is created to:
    - Flag spam detected by spam detection system
    - Flag profanity detected by profanity filter
    
    Flags are created by the "system" user to distinguish them from
    user-initiated flags.
    """
    from django_comments.models import CommentFlag
    from django_comments.utils import get_or_create_system_user, process_comment_content
    from django_comments.signals import comment_flagged, safe_send
    from django.contrib.contenttypes.models import ContentType
    import logging
    from django_comments.conf import comments_settings
    
    logger = logging.getLogger(comments_settings.LOGGER_NAME)
    
    system_user = get_or_create_system_user()
    
    # Get content analysis
    _, flags_to_apply = process_comment_content(comment.content)
    
    comment_ct = ContentType.objects.get_for_model(comment)
    
    # Apply spam flag if needed
    if flags_to_apply.get('auto_flag_spam'):
        try:
            reason = (
                flags_to_apply.get('spam_reason') or 
                'Automatically flagged by spam detection system'
            )
            
            # CRITICAL FIX: Proper UUID-to-string conversion
            flag, created = CommentFlag.objects.get_or_create(
                comment_type=comment_ct,
                comment_id=str(comment.pk),  # CRITICAL: Convert to string
                user=system_user,
                flag='spam',
                defaults={'reason': reason}
            )
            
            if created:
                logger.info(f"Auto-flagged comment {comment.pk} as spam. Reason: {reason}")
                
                # Send signal
                safe_send(
                    comment_flagged,
                    sender=CommentFlag,
                    flag=flag,
                    comment=comment,
                    user=system_user,
                    flag_type='spam',
                    reason=reason
                )
        except Exception as e:
            logger.error(f"Failed to create spam flag for comment {comment.pk}: {e}")
    
    # Apply profanity flag if needed
    if flags_to_apply.get('auto_flag_profanity'):
        try:
            reason = 'Automatically flagged for profanity'
            
            # CRITICAL FIX: Proper UUID-to-string conversion
            flag, created = CommentFlag.objects.get_or_create(
                comment_type=comment_ct,
                comment_id=str(comment.pk),  # CRITICAL: Convert to string
                user=system_user,
                flag='offensive',
                defaults={'reason': reason}
            )
            
            if created:
                logger.info(f"Auto-flagged comment {comment.pk} for profanity")
                
                # Send signal
                safe_send(
                    comment_flagged,
                    sender=CommentFlag,
                    flag=flag,
                    comment=comment,
                    user=system_user,
                    flag_type='offensive',
                    reason=reason
                )
        except Exception as e:
            logger.error(f"Failed to create profanity flag for comment {comment.pk}: {e}")




def get_comment_context(obj: models.Model) -> Dict[str, Any]:
    """Get context data for rendering comments for an object."""
    Comment = get_comment_model()
    content_type = ContentType.objects.get_for_model(obj)

    return {
        'object': obj,
        'content_type': content_type,
        'content_type_id': content_type.id,
        'app_label': content_type.app_label,
        'model_name': content_type.model,
        'object_id': str(obj.pk),  
        'comments': Comment.objects.filter(
            content_type=content_type,
            object_id=str(obj.pk),
            is_public=True,
            is_removed=False
        ).order_by('-created_at'),
    }


def check_comment_permissions(user, comment_or_object, action='view'):
    """Check if a user has permission to perform an action on a comment or object."""
    if user.is_anonymous:
        if action == 'view':
            if hasattr(comment_or_object, 'is_public'):
                return comment_or_object.is_public and not comment_or_object.is_removed
            return True
        elif action == 'add':
            return comments_settings.ALLOW_ANONYMOUS
        return False

    if user.is_staff or user.is_superuser:
        return True

    if action in ['moderate', 'change']:
        user_groups = user.groups.values_list('name', flat=True)
        for group in comments_settings.AUTO_APPROVE_GROUPS:
            if group in user_groups:
                return True

    if action == 'view':
        if hasattr(comment_or_object, 'is_public'):
            if comment_or_object.is_public and not comment_or_object.is_removed:
                return True
            user_groups = user.groups.values_list('name', flat=True)
            for group in comments_settings.CAN_VIEW_NON_PUBLIC_COMMENTS:
                if group in user_groups:
                    return True
            return comment_or_object.user == user
        return True

    if action == 'add':
        return True

    if action in ['change', 'delete']:
        return hasattr(comment_or_object, 'user') and comment_or_object.user == user

    return False



def check_flag_abuse(user):
    """
    Check if user is abusing the flag system.
    
    Args:
        user: User instance
    
    Returns:
        tuple: (is_abuse: bool, reason: str or None)
    
    Raises:
        RateLimitExceeded: If user exceeds flag limits
    """
    from .models import CommentFlag
    from .exceptions import RateLimitExceeded
    
    if not user or not user.is_authenticated:
        return False, None
    
    # Check daily limit
    daily_limit = comments_settings.MAX_FLAGS_PER_DAY
    if daily_limit:
        daily_count = CommentFlag.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(days=1)
        ).count()
        
        if daily_count >= daily_limit:
            raise RateLimitExceeded(
                message=f"You have exceeded the daily flag limit of {daily_limit}.",
                retry_after=86400  # 24 hours
            )
    
    # Check hourly limit
    hourly_limit = comments_settings.MAX_FLAGS_PER_HOUR
    if hourly_limit:
        hourly_count = CommentFlag.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if hourly_count >= hourly_limit:
            raise RateLimitExceeded(
                message=f"You have exceeded the hourly flag limit of {hourly_limit}.",
                retry_after=3600  # 1 hour
            )
    
    return False, None


def should_auto_approve_user(user):
    """
    Check if user should bypass moderation.
    
    A user bypasses moderation if they meet ANY of these criteria:
    1. Staff or superuser
    2. Member of AUTO_APPROVE_GROUPS (e.g., 'Moderators', 'Staff')
    3. Member of TRUSTED_USER_GROUPS (e.g., 'Verified', 'Premium')
    4. Has N or more approved comments (AUTO_APPROVE_AFTER_N_APPROVED)
    
    Args:
        user: User instance
    
    Returns:
        bool: True if user should be auto-approved
    """
    if not user or not user.is_authenticated:
        return False
    
    # Staff always auto-approved
    if user.is_staff or user.is_superuser:
        return True
    
    # Check AUTO_APPROVE_GROUPS (for moderators and staff groups)
    auto_approve_groups = comments_settings.AUTO_APPROVE_GROUPS
    if auto_approve_groups:
        user_groups = set(user.groups.values_list('name', flat=True))
        if user_groups & set(auto_approve_groups):
            return True
    
    # Check TRUSTED_USER_GROUPS (for verified/premium users)
    trusted_groups = comments_settings.TRUSTED_USER_GROUPS
    if trusted_groups:
        user_groups = set(user.groups.values_list('name', flat=True))
        if user_groups & set(trusted_groups):
            return True
    
    # Check approval history
    auto_approve_threshold = comments_settings.AUTO_APPROVE_AFTER_N_APPROVED
    if auto_approve_threshold:
        Comment = get_comment_model()
        approved_count = Comment.objects.filter(
            user=user,
            is_public=True,
            is_removed=False
        ).count()
        
        if approved_count >= auto_approve_threshold:
            return True
    
    return False


def get_or_create_system_user():
    """
    Get or create the system user atomically.
    
    This is the single source of truth for system user creation.
    
    The system user is used for:
    - Automatic spam/profanity flagging
    - Auto-ban actions
    - System-initiated moderation
    
    Returns:
        User: The system user instance
    
    Example:
        >>> system_user = get_or_create_system_user()
        >>> flag = CommentFlag.objects.create(
        ...     comment=comment,
        ...     user=system_user,
        ...     flag='spam'
        ... )
    
    Notes:
        - User is created with is_active=False to prevent login
        - User has no password set (cannot authenticate)
        - Multiple processes calling this simultaneously is safe
        - Uses database-level atomicity to prevent duplicates
    """
    try:
        system_user, created = User.objects.get_or_create(
            username='system',
            defaults={
                'email': 'system@django-comments.local',
                'is_active': False,  # Prevent login
                'first_name': 'System',
                'last_name': 'User',
            }
        )
        
        if created:
            logger.info("Created system user for automatic operations")
        
        return system_user
        
    except IntegrityError as e:
        # Should never happen with get_or_create, but handle it
        logger.error(f"IntegrityError creating system user: {e}")
        
        # Try to get the existing user
        try:
            system_user = User.objects.get(username='system')
            logger.info("Retrieved existing system user after IntegrityError")
            return system_user
        except User.DoesNotExist:
            # This should really never happen
            logger.critical("Cannot create or retrieve system user!")
            raise
    
    except Exception as e:
        logger.error(f"Unexpected error getting system user: {e}")
        raise

def check_flag_threshold(comment):
    """
    Check if comment has exceeded flag thresholds and take action.
    
    Args:
        comment: Comment instance to check
    
    This function is called after a comment is flagged to check if it should be:
    - Auto-hidden (based on AUTO_HIDE_THRESHOLD setting)
    - Auto-deleted (based on AUTO_DELETE_THRESHOLD setting)
    - Trigger moderator notification (based on FLAG_NOTIFICATION_THRESHOLD setting)
    
    Returns:
        dict: Dictionary with keys:
            - 'flag_count': Current flag count
            - 'auto_hidden': Boolean indicating if comment was auto-hidden
            - 'notified': Boolean indicating if moderators were notified
            - 'flag_obj': The most recent flag object (if available)
    """
    from django_comments.models import CommentFlag
    from django.contrib.contenttypes.models import ContentType
    from django_comments.utils import log_moderation_action, get_or_create_system_user
    
    logger = logging.getLogger(comments_settings.LOGGER_NAME)
    
    comment_ct = ContentType.objects.get_for_model(comment)
    
    # Get flag count and most recent flag
    # CRITICAL FIX: Use 'created_at' not 'created'
    flags = CommentFlag.objects.filter(
        comment_type=comment_ct,
        comment_id=str(comment.pk)  # CRITICAL: Convert to string
    ).order_by('-created_at')  # FIXED: Was '-created', now '-created_at'
    
    flag_count = flags.count()
    most_recent_flag = flags.first() if flags.exists() else None
    
    result = {
        'flag_count': flag_count,
        'auto_hidden': False,
        'notified': False,
        'flag_obj': most_recent_flag
    }
    
    # Check auto-hide threshold
    auto_hide_threshold = comments_settings.AUTO_HIDE_THRESHOLD
    if auto_hide_threshold and flag_count >= auto_hide_threshold:
        if comment.is_public and not comment.is_removed:
            comment.is_public = False
            comment.save(update_fields=['is_public'])
            
            system_user = get_or_create_system_user()
            log_moderation_action(
                comment=comment,
                moderator=system_user,
                action='rejected',
                reason=f'Auto-hidden: exceeded flag threshold ({flag_count} flags)'
            )
            
            logger.info(f"Auto-hid comment {comment.pk} due to {flag_count} flags")
            result['auto_hidden'] = True
            
            # Notify moderators if enabled
            if comments_settings.NOTIFY_ON_AUTO_HIDE:
                try:
                    from django_comments.notifications import notify_auto_hide
                    notify_auto_hide(comment, flag_count)
                except Exception as e:
                    logger.error(f"Error sending auto-hide notification: {e}")
    
    # Check auto-delete threshold
    auto_delete_threshold = comments_settings.AUTO_DELETE_THRESHOLD
    if auto_delete_threshold and flag_count >= auto_delete_threshold:
        logger.warning(
            f"Comment {comment.pk} reached auto-delete threshold "
            f"({flag_count} flags) but auto-delete is not implemented"
        )
    
    # Notify moderators at flag threshold
    flag_notification_threshold = comments_settings.FLAG_NOTIFICATION_THRESHOLD
    if flag_notification_threshold and flag_count >= flag_notification_threshold:
        if most_recent_flag:
            try:
                from django_comments.notifications import notify_moderators_of_flag
                notify_moderators_of_flag(comment, most_recent_flag, flag_count)
                result['notified'] = True
            except Exception as e:
                logger.error(f"Error sending flag notification: {e}")
    
    return result





def can_edit_comment(comment, user):
    """
    Check if user can edit a comment.
    
    Args:
        comment: Comment instance
        user: User instance
    
    Returns:
        tuple: (can_edit: bool, reason: str or None)
    """
    if not comments_settings.ALLOW_COMMENT_EDITING:
        return False, "Comment editing is disabled"
    
    # Only owner can edit (unless staff)
    if comment.user != user and not (user.is_staff or user.is_superuser):
        return False, "You can only edit your own comments"
    
    # Check edit time window
    edit_window = comments_settings.EDIT_TIME_WINDOW
    if edit_window:
        time_since_creation = (timezone.now() - comment.created_at).total_seconds()
        if time_since_creation > edit_window:
            return False, f"Edit window of {edit_window // 60} minutes has expired"
    
    # Can't edit removed comments
    if comment.is_removed:
        return False, "Cannot edit removed comments"
    
    return True, None


def create_comment_revision(comment, edited_by):
    """
    Create a revision before editing a comment.
    
    Args:
        comment: Comment instance
        edited_by: User making the edit
    
    Returns:
        CommentRevision instance or None
    """
    if not comments_settings.TRACK_EDIT_HISTORY:
        return None
    
    from .models import CommentRevision
    from django.contrib.contenttypes.models import ContentType
    
    try:
        revision = CommentRevision.objects.create(
            comment_type=ContentType.objects.get_for_model(comment),
            comment_id=str(comment.pk),
            content=comment.content,
            edited_by=edited_by,
            was_public=comment.is_public,
            was_removed=comment.is_removed
        )
        logger.info(f"Created revision for comment {comment.pk}")
        return revision
    except Exception as e:
        logger.error(f"Failed to create revision: {e}")
        return None


def log_moderation_action(comment, moderator, action, reason='', affected_user=None, ip_address=None):
    """
    Log a moderation action.
    
    Args:
        comment: Comment instance (can be None for user bans)
        moderator: User performing the action
        action: Action type
        reason: Reason for action
        affected_user: User affected by action (for bans)
        ip_address: IP address of moderator
    
    Returns:
        ModerationAction instance
    """
    from .models import ModerationAction
    from django.contrib.contenttypes.models import ContentType
    
    try:
        action_data = {
            'moderator': moderator,
            'action': action,
            'reason': reason,
            'affected_user': affected_user,
            'ip_address': ip_address,
        }
        
        if comment:
            action_data['comment_type'] = ContentType.objects.get_for_model(comment)
            action_data['comment_id'] = str(comment.pk)
        
        mod_action = ModerationAction.objects.create(**action_data)
        logger.info(f"Logged moderation action: {action} by {moderator}")
        return mod_action
    except Exception as e:
        logger.error(f"Failed to log moderation action: {e}")
        return None


def check_auto_ban_conditions(user):
    """
    Check if user should be auto-banned based on their history.
    
    Checks two conditions:
    1. Number of rejected comments (is_removed=True)
    2. Number of spam flags on user's comments
    
    Args:
        user: User instance to check
    
    Returns:
        tuple: (should_ban: bool, reason: str or None)
        
    Example:
        >>> should_ban, reason = check_auto_ban_conditions(user)
        >>> if should_ban:
        >>>     auto_ban_user(user, reason)
    
    Settings used:
        - AUTO_BAN_AFTER_REJECTIONS: Number of rejected comments before auto-ban
        - AUTO_BAN_AFTER_SPAM_FLAGS: Number of spam flags before auto-ban
    
    Notes:
        - Returns (False, None) if user is None or not authenticated
        - Checks rejections first, then spam flags
        - Returns on first threshold exceeded
        - Does not ban staff or superusers (checked in auto_ban_user)
    """
    from .models import CommentFlag
    from django.contrib.contenttypes.models import ContentType
    
    Comment = get_comment_model()
    
    # Validate user
    if not user or not user.is_authenticated:
        return False, None
    
    # Don't check staff/superusers (they won't be banned anyway)
    if user.is_staff or user.is_superuser:
        return False, None
    
    
    rejection_threshold = comments_settings.AUTO_BAN_AFTER_REJECTIONS
    if rejection_threshold:
        rejected_count = Comment.objects.filter(
            user=user,
            is_removed=True
        ).count()
        
        if rejected_count >= rejection_threshold:
            return True, f"Auto-ban: {rejected_count} rejected comments"
    
    spam_threshold = comments_settings.AUTO_BAN_AFTER_SPAM_FLAGS
    if spam_threshold:
        # Get Comment content type
        comment_ct = ContentType.objects.get_for_model(Comment)
        
        user_comment_ids = [
            str(pk) for pk in Comment.objects.filter(user=user).values_list('pk', flat=True)
        ]
        
        if user_comment_ids:
            spam_flags = CommentFlag.objects.filter(
                comment_type=comment_ct,
                comment_id__in=user_comment_ids,
                flag='spam'
            ).count()
            
            if spam_flags >= spam_threshold:
                return True, f"Auto-ban: {spam_flags} spam flags"
    
    # No ban conditions met
    return False, None



def auto_ban_user(user, reason: str) -> Optional['BannedUser']:
    """
    Automatically ban a user based on their behavior.
    
    This function is called when a user exceeds thresholds for:
    - Number of rejected comments
    - Number of spam flags
    - Other automatic ban conditions
    
    Args:
        user: User instance to ban
        reason: Detailed reason for the ban
    
    Returns:
        BannedUser instance if successful, None if failed
    
    Example:
        >>> user = User.objects.get(username='spammer')
        >>> ban = auto_ban_user(user, "Auto-ban: 5 spam flags")
        >>> if ban:
        >>>     print(f"User banned until {ban.banned_until}")
    
    Notes:
        - Ban duration is controlled by DEFAULT_BAN_DURATION_DAYS setting
        - If duration is None, creates permanent ban
        - Logs moderation action for audit trail
        - Sends notification email to banned user
        - Does not raise exceptions - returns None on failure
    """
    from .models import BannedUser
    
    # Validate input
    if not user or not user.is_authenticated:
        logger.warning("Attempted to ban invalid user")
        return None
    
    try:
        system_user = get_or_create_system_user()
        
        # Calculate ban duration
        ban_duration = comments_settings.DEFAULT_BAN_DURATION_DAYS
        banned_until = None
        
        if ban_duration:
            banned_until = timezone.now() + timedelta(days=ban_duration)
            logger.info(
                f"Auto-banning user {user.pk} for {ban_duration} days. "
                f"Reason: {reason}"
            )
        else:
            logger.warning(
                f"Auto-banning user {user.pk} PERMANENTLY. "
                f"Reason: {reason}"
            )
        
        existing_ban = BannedUser.objects.filter(
            user=user,
            banned_until__isnull=True  # Permanent
        ).first() or BannedUser.objects.filter(
            user=user,
            banned_until__gt=timezone.now()  # Active temporary
        ).first()
        
        if existing_ban:
            logger.info(
                f"User {user.pk} is already banned. "
                f"Skipping auto-ban. Existing reason: {existing_ban.reason}"
            )
            return existing_ban
        
        # Create the ban
        with transaction.atomic():
            ban = BannedUser.objects.create(
                user=user,
                banned_until=banned_until,
                reason=reason,
                banned_by=system_user
            )
            
            # Log moderation action
            log_moderation_action(
                comment=None,  # No specific comment
                moderator=system_user,
                action='banned_user',
                reason=reason,
                affected_user=user
            )
        
        logger.warning(
            f"Successfully auto-banned user {user.pk} "
            f"({'permanent' if not banned_until else f'until {banned_until}'})"
        )
        
        if comments_settings.SEND_NOTIFICATIONS:
            try:
                from .notifications import notify_user_banned
                notify_user_banned(ban)
                logger.info(f"Sent ban notification to user {user.pk}")
            except Exception as e:
                # Don't fail ban if email fails
                logger.error(
                    f"Failed to send ban notification to user {user.pk}: {e}",
                    exc_info=True
                )
        
        return ban
        
    except IntegrityError as e:
        # Possible duplicate ban attempt
        logger.error(
            f"IntegrityError auto-banning user {user.pk}: {e}. "
            "Checking for existing ban..."
        )
        
        # Try to return existing ban
        try:
            existing_ban = BannedUser.objects.filter(user=user).first()
            if existing_ban:
                logger.info(f"Found existing ban for user {user.pk}")
                return existing_ban
        except Exception:
            pass
        
        return None
        
    except Exception as e:
        # Log error but don't crash
        logger.error(
            f"Failed to auto-ban user {user.pk}: {e}",
            exc_info=True
        )
        return None

    
# ============================================================================
# UTILITY FUNCTIONS FOR BULK OPERATIONS
# ============================================================================

def bulk_create_flags_without_validation(flag_data_list):
    """
    FIXED: Bulk create flags without running validation.
    
    Replace your bulk_create_flags_without_validation() function in utils.py 
    with this complete function (if you have this function).
    
    Args:
        flag_data_list: List of dicts with flag data
        
    Returns:
        List of created CommentFlag instances
    
    Example:
        flag_data = [
            {
                'comment_type': comment_ct,
                'comment_id': str(comment.pk),
                'user': user,
                'flag': 'spam'
            }
        ]
        flags = bulk_create_flags_without_validation(flag_data)
    """
    from django_comments.models import CommentFlag
    import logging
    from django_comments.conf import comments_settings
    
    logger = logging.getLogger(comments_settings.LOGGER_NAME)
    
    if not flag_data_list:
        return []
    
    # CRITICAL FIX: Ensure all comment_ids are strings
    for flag_data in flag_data_list:
        if 'comment_id' in flag_data:
            flag_data['comment_id'] = str(flag_data['comment_id'])
    
    flags = []
    for flag_data in flag_data_list:
        flag = CommentFlag(**flag_data)
        flags.append(flag)
    
    # Bulk create without calling save() (skips validation)
    created_flags = CommentFlag.objects.bulk_create(flags)
    
    logger.info(f"Bulk created {len(created_flags)} flags")
    
    return created_flags


# ============================================================================
# SAFE CONTEXT MANAGER FOR BULK OPERATIONS
# ============================================================================

@contextmanager
def skip_flag_validation():
    """
    Context manager for safely skipping flag validation in bulk operations.
    
    This should ONLY be used when:
    1. You're doing bulk operations with pre-validated data
    2. You need maximum performance
    3. You're confident the data is correct
    
    Usage:
        from django_comments.models import CommentFlag
        from django_comments.utils import skip_flag_validation
        
        flags = []
        for data in validated_flag_data:
            flag = CommentFlag(**data)
            flags.append(flag)
        
        with skip_flag_validation():
            CommentFlag.objects.bulk_create(flags)
    
    Security:
        This context manager properly manages the validation flag
        and ensures it's always cleaned up, even if an exception occurs.
    """
    # Store original flag state (shouldn't exist, but be safe)
    original_state = {}
    
    try:
        # Enable skip for all new CommentFlag instances
        CommentFlag._bulk_create_skip_validation = True
        yield
    finally:
        # Always clean up, even if exception occurred
        CommentFlag._bulk_create_skip_validation = False


def warm_caches_for_queryset(queryset, request=None):
    """
    Batch warm all relevant caches for a queryset of comments.
    
    This is useful for:
    - Pre-populating caches before serving a page
    - Warming caches in background tasks
    - Preparing data for high-traffic endpoints
    
    Args:
        queryset: Comment queryset to warm caches for
        request: Optional request object for context
    
    Example:
        from django_comments.api.views import warm_caches_for_queryset
        
        # Before serving dashboard
        recent_comments = Comment.objects.all()[:100]
        warm_caches_for_queryset(recent_comments)
    """
    if not queryset:
        return
    
    # Convert to list to evaluate queryset once
    comments = list(queryset)
    
    if not comments:
        return
    
    # Warm comment count caches
    content_objects = {}
    for comment in comments:
        if comment.content_object:
            key = (comment.content_type.pk, comment.object_id)
            if key not in content_objects:
                content_objects[key] = comment.content_object
    
    # Batch warm comment counts
    for obj in content_objects.values():
        from ..cache import get_comment_count_for_object
        get_comment_count_for_object(obj, public_only=True)
        get_comment_count_for_object(obj, public_only=False)
    
    # Warm flag counts
    comment_ids = [str(c.pk) for c in comments]
    from ..models import CommentFlag
    
    flag_counts = CommentFlag.objects.filter(
        comment_id__in=comment_ids
    ).values('comment_id').annotate(
        count=Count('id')
    )
    
    for item in flag_counts:
        cache_key = f"comment_flag_count:{item['comment_id']}"
        cache.set(cache_key, item['count'], 3600)