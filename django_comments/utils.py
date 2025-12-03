import re
import logging
import importlib
from typing import List, Dict, Any, Type, Union, Optional
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.db import models
from .conf import comments_settings
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

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
    
    IMPROVED: Better error handling and multiple lookup strategies.
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
            # Try lowercase model name
            try:
                model = apps.get_model(app_label, model_name.lower())
                if model:
                    models_list.append(model)
                    logger.debug(f"Loaded model '{model_path}' with lowercase: {app_label}.{model_name.lower()}")
                    continue
            except (ValueError, LookupError) as e:
                logger.debug(f"Lowercase attempt failed for '{model_path}': {e}")
            
            # Try original case
            try:
                model = apps.get_model(app_label, model_name)
                if model:
                    models_list.append(model)
                    logger.debug(f"Loaded model '{model_path}' with original case: {app_label}.{model_name}")
                    continue
            except (ValueError, LookupError) as e:
                logger.debug(f"Original case attempt failed for '{model_path}': {e}")

        # Strategy 3: Try module.path.ModelClass format
        try:
            if model_path.count('.') >= 2:  # Has at least module.submodule.Class
                module_path, class_name = model_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
                model = getattr(module, class_name)
                if model and issubclass(model, models.Model):
                    models_list.append(model)
                    logger.debug(f"Loaded model '{model_path}' via import: {module_path}.{class_name}")
                    continue
        except (ImportError, AttributeError, ValueError, TypeError) as e:
            logger.debug(f"Import attempt failed for '{model_path}': {e}")
        
        # If we got here, all strategies failed
        logger.error(f"Could not load model '{model_path}' using any strategy. "
                    f"Available apps: {list(apps.app_configs.keys())}")

    if not models_list:
        logger.warning(f"No models could be loaded from COMMENTABLE_MODELS: {model_paths}")
    else:
        logger.info(f"Successfully loaded {len(models_list)} commentable models: "
                   f"{[m._meta.label for m in models_list]}")

    return models_list


def get_commentable_content_types() -> List[ContentType]:
    """
    Return a list of content types for commentable models.
    """
    models_list = get_commentable_models()
    return [ContentType.objects.get_for_model(model) for model in models_list]


def get_model_from_content_type_string(content_type_str: str) -> Optional[Type[models.Model]]:
    """
    Convert a string like 'app_label.ModelName' to a model class.
    """
    try:
        return apps.get_model(content_type_str)
    except (ValueError, LookupError) as e:
        logger.error(f"Invalid content type string: {content_type_str}. Error: {e}")
        return None


def get_object_from_content_type_and_id(content_type_str: str, obj_id: Union[str, int]) -> Optional[models.Model]:
    """
    Get a model instance from a content type string and object ID.
    """
    model = get_model_from_content_type_string(content_type_str)
    if not model:
        return None

    try:
        return model.objects.get(pk=obj_id)
    except ObjectDoesNotExist:
        logger.error(f"Object with ID {obj_id} not found for model {content_type_str}")
        return None


def is_comment_content_allowed(content: str) -> bool:
    """
    Check if comment content is allowed (not spam, not profane, etc.)
    """
    if not content or len(content) > comments_settings.MAX_COMMENT_LENGTH:
        return False

    content_lower = content.lower()

    # Spam detection
    if comments_settings.SPAM_DETECTION_ENABLED and comments_settings.SPAM_WORDS:
        for word in comments_settings.SPAM_WORDS:
            if word.lower() in content_lower:
                return False

    # Profanity filtering
    if comments_settings.PROFANITY_FILTERING and comments_settings.PROFANITY_LIST:
        for word in comments_settings.PROFANITY_LIST:
            if word.lower() in content_lower:
                if comments_settings.PROFANITY_ACTION in ['hide', 'delete']:
                    return False

    return True


def filter_profanity(content: str) -> str:
    """
    Filter profanity from comment content by replacing words with asterisks.
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


def get_comment_context(obj: models.Model) -> Dict[str, Any]:
    """
    Get context data for rendering comments for an object.
    """
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
    """
    Check if a user has permission to perform an action on a comment or object.
    """
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