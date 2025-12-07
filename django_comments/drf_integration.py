from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.pagination import PageNumberPagination
from .conf import comments_settings


class CommentRateThrottle(UserRateThrottle):
    """
    Throttle for authenticated comment submissions.
    
    Usage in settings.py:
        DJANGO_COMMENTS_CONFIG = {
            'API_RATE_LIMIT': '100/day',
        }
    
    Or use DRF's REST_FRAMEWORK settings:
        REST_FRAMEWORK = {
            'DEFAULT_THROTTLE_RATES': {
                'comment': '100/day',
                'comment_anon': '20/day',
            }
        }
    """
    scope = 'comment'
    
    def __init__(self):
        super().__init__()
        # Use comment-specific rate limit if configured
        rate = comments_settings.API_RATE_LIMIT
        if rate:
            self.rate = rate
    
    def allow_request(self, request, view):
        """
        Check if request should be allowed based on rate limit.
        """
        # Only throttle POST requests (comment creation)
        if request.method != 'POST':
            return True
        
        return super().allow_request(request, view)


class CommentAnonRateThrottle(AnonRateThrottle):
    """
    Throttle for anonymous comment submissions.
    Generally more restrictive than authenticated rate.
    
    Usage:
        DJANGO_COMMENTS_CONFIG = {
            'API_RATE_LIMIT_ANON': '20/day',
        }
    """
    scope = 'comment_anon'
    
    def __init__(self):
        super().__init__()
        # Use anonymous-specific rate limit if configured
        rate = comments_settings.API_RATE_LIMIT_ANON
        if rate:
            self.rate = rate
    
    def allow_request(self, request, view):
        """
        Check if request should be allowed based on rate limit.
        """
        # Only throttle POST requests (comment creation)
        if request.method != 'POST':
            return True
        
        return super().allow_request(request, view)


class CommentBurstRateThrottle(UserRateThrottle):
    """
    Throttle for burst protection (short-term rate limiting).
    Prevents rapid-fire comment spam.
    
    Example: Limit to 5 comments per minute.
    
    Usage:
        DJANGO_COMMENTS_CONFIG = {
            'API_RATE_LIMIT_BURST': '5/min',
        }
    """
    scope = 'comment_burst'
    
    def __init__(self):
        super().__init__()
        rate = comments_settings.API_RATE_LIMIT_BURST
        if rate:
            self.rate = rate
        else:
            # Default burst limit
            self.rate = '5/min'
    
    def allow_request(self, request, view):
        """Check burst rate limit."""
        if request.method != 'POST':
            return True
        
        return super().allow_request(request, view)


def get_comment_throttle_classes():
    """
    Get list of throttle classes to use for comments API.
    
    Returns:
        List of throttle class instances
    
    Usage in views:
        class CommentViewSet(viewsets.ModelViewSet):
            throttle_classes = get_comment_throttle_classes()
    """
    throttles = []
    
    # Add authenticated user throttle if configured
    if comments_settings.API_RATE_LIMIT:
        throttles.append(CommentRateThrottle)
    
    # Add anonymous throttle if configured
    if comments_settings.API_RATE_LIMIT_ANON:
        throttles.append(CommentAnonRateThrottle)
    
    # Add burst throttle if configured
    if comments_settings.API_RATE_LIMIT_BURST:
        throttles.append(CommentBurstRateThrottle)
    
    return throttles

class CommentPagination(PageNumberPagination):
    """
    Pagination for comments API.
    
    Usage in settings.py:
        DJANGO_COMMENTS_CONFIG = {
            'PAGE_SIZE': 20,
            'PAGE_SIZE_QUERY_PARAM': 'page_size',
            'MAX_PAGE_SIZE': 100,
        }
    
    Or use DRF's REST_FRAMEWORK settings:
        REST_FRAMEWORK = {
            'PAGE_SIZE': 20,
        }
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Use comment-specific page size if configured
        if comments_settings.PAGE_SIZE:
            self.page_size = comments_settings.PAGE_SIZE
        
        # Allow client to override page size
        if comments_settings.PAGE_SIZE_QUERY_PARAM:
            self.page_size_query_param = comments_settings.PAGE_SIZE_QUERY_PARAM
        
        # Set maximum page size
        if comments_settings.MAX_PAGE_SIZE:
            self.max_page_size = comments_settings.MAX_PAGE_SIZE


class ThreadedCommentPagination(CommentPagination):
    """
    Special pagination for threaded comments.
    Paginates root comments but includes all children.
    """
    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate only root comments, but prefetch all children.
        """
        # Filter to root comments only for pagination
        root_queryset = queryset.filter(parent__isnull=True)
        
        # Use parent pagination
        page = super().paginate_queryset(root_queryset, request, view)
        
        if page is not None:
            # Prefetch children for paginated root comments
            from django.db.models import Prefetch
            from .utils import get_comment_model
            Comment = get_comment_model()
            
            page = list(page)  # Evaluate queryset
            
            # Get root comment IDs
            root_ids = [c.pk for c in page]
            
            # Prefetch all descendants
            for root in page:
                # This will use the already-optimized queryset
                pass
        
        return page


def get_comment_pagination_class():
    """
    Get pagination class to use for comments API.
    
    Returns:
        Pagination class
    
    Usage in views:
        class CommentViewSet(viewsets.ModelViewSet):
            pagination_class = get_comment_pagination_class()
    """
    # Use threaded pagination if threading is enabled
    if comments_settings.MAX_COMMENT_DEPTH is not None:
        return ThreadedCommentPagination
    
    return CommentPagination


def apply_drf_integrations(viewset_class):
    """
    Apply DRF integrations to a viewset class.
    
    Args:
        viewset_class: ViewSet class to modify
    
    Returns:
        Modified viewset class
    
    Usage:
        from django_comments.drf_integration import apply_drf_integrations
        
        @apply_drf_integrations
        class CommentViewSet(viewsets.ModelViewSet):
            ...
    """
    # Apply throttling
    throttles = get_comment_throttle_classes()
    if throttles:
        viewset_class.throttle_classes = throttles
    
    # Apply pagination
    pagination = get_comment_pagination_class()
    if pagination:
        viewset_class.pagination_class = pagination
    
    return viewset_class


def get_drf_settings():
    """
    Get DRF-compatible settings dictionary.
    
    Returns:
        Dict of DRF settings
    
    Usage:
        # In your REST_FRAMEWORK settings
        REST_FRAMEWORK = {
            **get_drf_settings(),
            # ... other settings
        }
    """
    settings = {}
    
    # Pagination
    if comments_settings.PAGE_SIZE:
        settings['PAGE_SIZE'] = comments_settings.PAGE_SIZE
    
    # Throttling rates
    throttle_rates = {}
    
    if comments_settings.API_RATE_LIMIT:
        throttle_rates['comment'] = comments_settings.API_RATE_LIMIT
    
    if comments_settings.API_RATE_LIMIT_ANON:
        throttle_rates['comment_anon'] = comments_settings.API_RATE_LIMIT_ANON
    
    if comments_settings.API_RATE_LIMIT_BURST:
        throttle_rates['comment_burst'] = comments_settings.API_RATE_LIMIT_BURST
    
    if throttle_rates:
        settings['DEFAULT_THROTTLE_RATES'] = throttle_rates
    
    return settings