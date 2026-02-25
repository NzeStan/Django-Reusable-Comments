from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .conf import comments_settings
from .utils import get_comment_model

Comment = get_comment_model()

# Cache timeout in seconds (default 1 hour)
CACHE_TIMEOUT = getattr(comments_settings, 'CACHE_TIMEOUT', 3600)


def get_cache_key(prefix, content_type, object_id):
    """Generate a safe cache key."""
    safe_ct = str(content_type).replace(':', '_')
    safe_id = str(object_id).replace(':', '_')
    return f"django_comments:{prefix}:{safe_ct}:{safe_id}"


def get_comment_count_cache_key(content_object):
    """
    Get cache key for comment count of an object.
    """
    ct = ContentType.objects.get_for_model(content_object)
    return get_cache_key('count', f"{ct.app_label}.{ct.model}", content_object.pk)


def get_public_comment_count_cache_key(content_object):
    """
    Get cache key for public comment count of an object.
    """
    ct = ContentType.objects.get_for_model(content_object)
    return get_cache_key('public_count', f"{ct.app_label}.{ct.model}", content_object.pk)


def get_comment_count_for_object(content_object, public_only=True):
    """
    Get comment count for an object with caching.
    
    Args:
        content_object: The object to get comments for
        public_only: If True, only count public comments
    
    Returns:
        int: Number of comments
    """
    if public_only:
        cache_key = get_public_comment_count_cache_key(content_object)
    else:
        cache_key = get_comment_count_cache_key(content_object)
    
    # Try to get from cache
    count = cache.get(cache_key)
    
    if count is None:
        # Not in cache, calculate it
        ct = ContentType.objects.get_for_model(content_object)
        queryset = Comment.objects.filter(
            content_type=ct,
            object_id=content_object.pk
        )
        
        if public_only:
            queryset = queryset.filter(is_public=True, is_removed=False)
        
        count = queryset.count()
        
        # Store in cache
        cache.set(cache_key, count, CACHE_TIMEOUT)
    
    return count


def get_comment_counts_for_objects(model_class, object_ids, public_only=True):
    """
    Get comment counts for multiple objects efficiently.
    Uses cache and batches database queries.
    
    Args:
        model_class: The model class of the objects
        object_ids: List of object IDs (can be any type - will be converted to strings)
        public_only: If True, only count public comments
    
    Returns:
        dict: Mapping of object_id -> comment_count (keys match input object_ids type)
    """
    if not object_ids:
        return {}
    
    ct = ContentType.objects.get_for_model(model_class)
    prefix = 'public_count' if public_only else 'count'
    
    str_to_original = {}
    normalized_ids = []
    
    for obj_id in object_ids:
        str_id = str(obj_id)
        str_to_original[str_id] = obj_id
        normalized_ids.append(str_id)
    
    # Generate cache keys using string IDs
    cache_keys = {
        str_id: get_cache_key(prefix, f"{ct.app_label}.{ct.model}", str_id)
        for str_id in normalized_ids
    }
    
    # Get cached values
    cached_values = cache.get_many(cache_keys.values())
    
    # Map back to original object IDs
    result = {}
    missing_ids = []
    
    for str_id, cache_key in cache_keys.items():
        if cache_key in cached_values:
            # Return with original object_id type
            original_id = str_to_original[str_id]
            result[original_id] = cached_values[cache_key]
        else:
            missing_ids.append(str_id)
    
    # If some values are missing, query database
    if missing_ids:
        queryset = Comment.objects.filter(
            content_type=ct,
            object_id__in=missing_ids
        )
        
        if public_only:
            queryset = queryset.filter(is_public=True, is_removed=False)
        
        # Use values() and Count for efficiency
        from django.db.models import Count
        counts = queryset.values('object_id').annotate(
            count=Count('id')
        )
        
        # Update result and cache
        to_cache = {}
        for item in counts:
            str_id = item['object_id']  
            count = item['count']
            
            # Return with original object_id type
            original_id = str_to_original[str_id]
            result[original_id] = count
            to_cache[cache_keys[str_id]] = count
        
        # Set missing IDs to 0
        for str_id in missing_ids:
            if str_id not in [item['object_id'] for item in counts]:
                # Return with original object_id type
                original_id = str_to_original[str_id]
                result[original_id] = 0
                to_cache[cache_keys[str_id]] = 0
        
        # Cache the new values
        if to_cache:
            cache.set_many(to_cache, CACHE_TIMEOUT)
    
    return result


def invalidate_comment_cache(content_object):
    """
    Invalidate all comment-related caches for an object.
    
    Args:
        content_object: The object whose caches should be invalidated
    """
    cache_keys = [
        get_comment_count_cache_key(content_object),
        get_public_comment_count_cache_key(content_object),
    ]
    cache.delete_many(cache_keys)


def invalidate_comment_cache_by_comment(comment):
    """
    Invalidate caches based on a comment instance.

    Args:
        comment: Comment instance
    """
    try:
        content_object = comment.content_object
    except (ValueError, TypeError):
        # object_id format is incompatible with the content type's pk field
        content_object = None

    if content_object:
        invalidate_comment_cache(content_object)
    else:
        # If content_object is None (deleted or invalid id), clear by content_type and object_id
        ct = comment.content_type
        cache_keys = [
            get_cache_key('count', f"{ct.app_label}.{ct.model}", comment.object_id),
            get_cache_key('public_count', f"{ct.app_label}.{ct.model}", comment.object_id),
        ]
        cache.delete_many(cache_keys)


# Signal handlers for automatic cache invalidation
@receiver(post_save, sender=Comment)
def invalidate_cache_on_save(sender, instance, created, **kwargs):
    """
    Invalidate cache when a comment is saved.
    """
    invalidate_comment_cache_by_comment(instance)


@receiver(post_delete, sender=Comment)
def invalidate_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate cache when a comment is deleted.
    """
    invalidate_comment_cache_by_comment(instance)


def warm_comment_cache_for_queryset(queryset, model_field='pk'):
    """
    Pre-populate comment count cache for a queryset of objects.
    Useful for list views where you'll be displaying comment counts.
    
    Args:
        queryset: QuerySet of objects to warm cache for
        model_field: Field name to use as object_id (default 'pk')
    
    Example:
        posts = Post.objects.all()[:20]
        warm_comment_cache_for_queryset(posts)
        # Now comment counts for these posts are cached
    """
    if not queryset:
        return
    
    model_class = queryset.model
    object_ids = list(queryset.values_list(model_field, flat=True))
    
    # This will cache the counts
    get_comment_counts_for_objects(model_class, object_ids, public_only=True)
    get_comment_counts_for_objects(model_class, object_ids, public_only=False)


def get_or_set_cache(key, callable_func, timeout=CACHE_TIMEOUT):
    """
    Generic cache get-or-set pattern.
    
    Args:
        key: Cache key
        callable_func: Function to call if cache miss
        timeout: Cache timeout in seconds
    
    Returns:
        Cached or computed value
    """
    value = cache.get(key)
    if value is None:
        value = callable_func()
        cache.set(key, value, timeout)
    return value


# Template tag helper (optional)
def get_comment_count_for_template(obj):
    """
    Helper for template tags to get comment count.
    """
    return get_comment_count_for_object(obj, public_only=True)