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