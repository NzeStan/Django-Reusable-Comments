import re
import logging
import importlib
from typing import List, Dict, Any, Type, Union, Optional, Tuple
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.db import models
from .conf import comments_settings
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
logger = logging.getLogger(comments_settings.LOGGER_NAME)


def get_comment_model():
    """
    Return the Comment model that is active in this project.
    
    This checks the DJANGO_COMMENTS_COMMENT_MODEL setting, which is
    automatically set by AppConfig.ready() based on USE_UUIDS.
    
    Returns either Comment or UUIDComment.
    """
    model_string = getattr(
        settings,
        'DJANGO_COMMENTS_COMMENT_MODEL',
        'django_comments.Comment'  # Default fallback
    )
    
    try:
        return apps.get_model(model_string, require_ready=False)
    except (ValueError, LookupError) as e:
        raise ImproperlyConfigured(
            f"Could not load comment model '{model_string}'. "
            "Check your DJANGO_COMMENTS_CONFIG['USE_UUIDS'] setting."
        ) from e


def get_comment_model_path() -> str:
    """
    Return the path to the comment model.
    Used for ForeignKey string references.
    """
    return getattr(
        settings,
        'DJANGO_COMMENTS_COMMENT_MODEL',
        'django_comments.Comment'
    )


def get_commentable_models() -> List[Type[models.Model]]:
    """
    Return a list of model classes that can be commented on.
    Accepts either 'app_label.ModelName' or 'module.path.ModelClass'.
    """
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
    """Convert a string like 'app_label.ModelName' to a model class."""
    try:
        return apps.get_model(content_type_str)
    except (ValueError, LookupError) as e:
        logger.error(f"Invalid content type string: {content_type_str}. Error: {e}")
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
    Check if comment content is allowed (not spam, not profane, etc.)
    
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
            if action in ['hide', 'delete']:
                return False, f"Content flagged as spam: {spam_reason}"
            # If action is 'flag', we allow it but mark for flagging

    # Check for profanity
    if comments_settings.PROFANITY_FILTERING:
        has_profanity = check_content_for_profanity(content)
        if has_profanity:
            action = comments_settings.PROFANITY_ACTION
            if action in ['hide', 'delete']:
                return False, f"Content contains profanity"
            # If action is 'censor' or 'flag', we allow it (will be processed later)

    return True, None


def process_comment_content(content: str) -> tuple[str, dict]:
    """
    Process comment content for spam and profanity.
    
    This is called during comment creation to:
    1. Filter profanity (if action is 'censor')
    2. Determine flags to apply (if action is 'flag')
    
    Returns:
        tuple: (processed_content: str, flags_to_apply: dict)
               flags_to_apply contains metadata about detected issues
    """
    processed_content = content
    flags_to_apply = {
        'is_spam': False,
        'has_profanity': False,
        'auto_flag_spam': False,
        'auto_flag_profanity': False,
        'spam_reason': None,
    }
    
    # Check spam
    if comments_settings.SPAM_DETECTION_ENABLED:
        is_spam, spam_reason = check_content_for_spam(content)
        if is_spam:
            flags_to_apply['is_spam'] = True
            flags_to_apply['spam_reason'] = spam_reason
            if comments_settings.SPAM_ACTION == 'flag':
                flags_to_apply['auto_flag_spam'] = True
                logger.info(f"Content will be auto-flagged as spam: {spam_reason}")
    
    # Check and process profanity
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
    
    return processed_content, flags_to_apply


def apply_automatic_flags(comment):
    """
    Apply automatic flags to a comment based on content analysis.
    
    Args:
        comment: Comment instance
    """
    from .models import CommentFlag
    from django.contrib.auth import get_user_model
    
    # Get system user for automatic flags
    User = get_user_model()
    system_user, _ = User.objects.get_or_create(
        username='system',
        defaults={
            'email': 'system@django-comments.local',
            'is_active': False,
        }
    )
    
    # Get content analysis
    _, flags_to_apply = process_comment_content(comment.content)
    
    # Apply spam flag if needed
    if flags_to_apply.get('auto_flag_spam'):
        try:
            reason = flags_to_apply.get('spam_reason') or 'Automatically flagged by spam detection system'
            CommentFlag.objects.create_or_get_flag(
                comment=comment,
                user=system_user,
                flag='spam',
                reason=reason
            )
            logger.info(f"Auto-flagged comment {comment.pk} as spam")
        except Exception as e:
            logger.error(f"Failed to auto-flag comment as spam: {e}")
    
    # Apply profanity flag if needed
    if flags_to_apply.get('auto_flag_profanity'):
        try:
            CommentFlag.objects.create_or_get_flag(
                comment=comment,
                user=system_user,
                flag='offensive',
                reason='Automatically flagged for profanity'
            )
            logger.info(f"Auto-flagged comment {comment.pk} for profanity")
        except Exception as e:
            logger.error(f"Failed to auto-flag comment for profanity: {e}")


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
        'object_id': obj.pk,
        'comments': Comment.objects.filter(
            content_type=content_type,
            object_id=obj.pk,
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

def check_user_banned(user):
    """
    Check if a user is banned from commenting.
    
    Args:
        user: User instance
    
    Returns:
        tuple: (is_banned: bool, ban_info: dict or None)
    """
    from .models import BannedUser
    
    if not user or not user.is_authenticated:
        return False, None
    
    # Check for active bans
    active_bans = BannedUser.objects.filter(
        user=user
    ).filter(
        models.Q(banned_until__isnull=True) |  # Permanent
        models.Q(banned_until__gt=timezone.now())  # Temporary still active
    ).first()
    
    if active_bans:
        ban_info = {
            'reason': active_bans.reason,
            'banned_until': active_bans.banned_until,
            'is_permanent': active_bans.banned_until is None,
            'banned_by': active_bans.banned_by,
        }
        return True, ban_info
    
    return False, None


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
    
    # Check trusted groups
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


def check_flag_threshold(comment):
    """
    Check if comment has exceeded flag thresholds and take action.
    
    Args:
        comment: Comment instance
    
    Returns:
        dict: Actions taken
    """
    from .models import ModerationAction
    
    flag_count = comment.flags.count()
    actions_taken = {
        'hidden': False,
        'deleted': False,
        'notified': False,
    }
    
    # Check delete threshold
    delete_threshold = comments_settings.AUTO_DELETE_THRESHOLD
    if delete_threshold and flag_count >= delete_threshold:
        # Log action
        ModerationAction.objects.create(
            comment=comment,
            moderator=None,  # System action
            action='deleted',
            reason=f'Auto-deleted after {flag_count} flags'
        )
        comment.delete()
        actions_taken['deleted'] = True
        logger.info(f"Auto-deleted comment {comment.pk} after {flag_count} flags")
        return actions_taken
    
    # Check hide threshold
    hide_threshold = comments_settings.AUTO_HIDE_THRESHOLD
    if hide_threshold and flag_count >= hide_threshold and comment.is_public:
        comment.is_public = False
        comment.save(update_fields=['is_public'])
        
        # Log action
        ModerationAction.objects.create(
            comment=comment,
            moderator=None,  # System action
            action='rejected',
            reason=f'Auto-hidden after {flag_count} flags'
        )
        
        actions_taken['hidden'] = True
        logger.info(f"Auto-hidden comment {comment.pk} after {flag_count} flags")
        
        # Notify moderators if enabled
        if comments_settings.NOTIFY_ON_AUTO_HIDE:
            from .notifications import notify_auto_hide
            notify_auto_hide(comment, flag_count)
            actions_taken['notified'] = True
    
    return actions_taken


def apply_automatic_flags(comment):
    """
    Apply automatic flags to a comment based on content analysis.
    ENHANCED: Now supports auto-hiding.
    
    Args:
        comment: Comment instance
    """
    from .models import CommentFlag, ModerationAction
    from django.contrib.auth import get_user_model
    
    # Get system user for automatic flags
    User = get_user_model()
    system_user, _ = User.objects.get_or_create(
        username='system',
        defaults={
            'email': 'system@django-comments.local',
            'is_active': False,
        }
    )
    
    # Get content analysis
    _, flags_to_apply = process_comment_content(comment.content)
    
    actions_taken = []
    
    # Apply spam flag if needed
    if flags_to_apply.get('auto_flag_spam'):
        try:
            reason = flags_to_apply.get('spam_reason') or 'Automatically flagged by spam detection system'
            CommentFlag.objects.create_or_get_flag(
                comment=comment,
                user=system_user,
                flag='spam',
                reason=reason
            )
            logger.info(f"Auto-flagged comment {comment.pk} as spam")
            actions_taken.append('spam_flagged')
            
            # Auto-hide if enabled
            if comments_settings.AUTO_HIDE_DETECTED_SPAM and comment.is_public:
                comment.is_public = False
                comment.save(update_fields=['is_public'])
                
                ModerationAction.objects.create(
                    comment=comment,
                    moderator=None,
                    action='rejected',
                    reason='Auto-hidden: Spam detected'
                )
                
                logger.info(f"Auto-hidden comment {comment.pk} (spam detected)")
                actions_taken.append('auto_hidden')
                
        except Exception as e:
            logger.error(f"Failed to auto-flag comment as spam: {e}")
    
    # Apply profanity flag if needed
    if flags_to_apply.get('auto_flag_profanity'):
        try:
            CommentFlag.objects.create_or_get_flag(
                comment=comment,
                user=system_user,
                flag='offensive',
                reason='Automatically flagged for profanity'
            )
            logger.info(f"Auto-flagged comment {comment.pk} for profanity")
            actions_taken.append('profanity_flagged')
            
            # Auto-hide if enabled
            if comments_settings.AUTO_HIDE_PROFANITY and comment.is_public:
                comment.is_public = False
                comment.save(update_fields=['is_public'])
                
                ModerationAction.objects.create(
                    comment=comment,
                    moderator=None,
                    action='rejected',
                    reason='Auto-hidden: Profanity detected'
                )
                
                logger.info(f"Auto-hidden comment {comment.pk} (profanity detected)")
                actions_taken.append('auto_hidden')
                
        except Exception as e:
            logger.error(f"Failed to auto-flag comment for profanity: {e}")
    
    return actions_taken


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
    
    Args:
        user: User instance
    
    Returns:
        tuple: (should_ban: bool, reason: str or None)
    """
    from .models import CommentFlag
    
    Comment = get_comment_model()
    
    # Check rejected comments
    rejection_threshold = comments_settings.AUTO_BAN_AFTER_REJECTIONS
    if rejection_threshold:
        rejected_count = Comment.objects.filter(
            user=user,
            is_removed=True
        ).count()
        
        if rejected_count >= rejection_threshold:
            return True, f"Auto-ban: {rejected_count} rejected comments"
    
    # Check spam flags
    spam_threshold = comments_settings.AUTO_BAN_AFTER_SPAM_FLAGS
    if spam_threshold:
        spam_flags = CommentFlag.objects.filter(
            comment__user=user,
            flag='spam'
        ).count()
        
        if spam_flags >= spam_threshold:
            return True, f"Auto-ban: {spam_flags} spam flags"
    
    return False, None


def auto_ban_user(user, reason):
    """
    Automatically ban a user.
    
    Args:
        user: User instance
        reason: Reason for ban
    
    Returns:
        BannedUser instance or None
    """
    from .models import BannedUser
    from django.contrib.auth import get_user_model
    
    try:
        # Get system user
        User = get_user_model()
        system_user, _ = User.objects.get_or_create(
            username='system',
            defaults={
                'email': 'system@django-comments.local',
                'is_active': False,
            }
        )
        
        # Calculate ban duration
        ban_duration = comments_settings.DEFAULT_BAN_DURATION_DAYS
        banned_until = None
        if ban_duration:
            banned_until = timezone.now() + timedelta(days=ban_duration)
        
        # Create ban
        ban = BannedUser.objects.create(
            user=user,
            banned_until=banned_until,
            reason=reason,
            banned_by=system_user
        )
        
        # Log action
        log_moderation_action(
            comment=None,
            moderator=system_user,
            action='banned_user',
            reason=reason,
            affected_user=user
        )
        
        logger.warning(f"Auto-banned user {user.pk}: {reason}")
        return ban
        
    except Exception as e:
        logger.error(f"Failed to auto-ban user: {e}")
        return None
