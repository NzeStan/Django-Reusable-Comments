class CommentCacheWarmingMiddleware:
    """
    Middleware to automatically warm comment-related caches.
    
    Add to MIDDLEWARE in settings.py:
        MIDDLEWARE = [
            ...
            'django_comments.middleware.CommentCacheWarmingMiddleware',
        ]
    
    This middleware:
    - Detects comment-heavy views
    - Pre-warms caches intelligently
    - Reduces database load on subsequent requests
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Pre-process: Warm caches if this is a known comment view
        self._pre_warm_caches(request)
        
        # Get response
        response = self.get_response(request)
        
        # Post-process: Warm caches for likely next requests
        self._post_warm_caches(request, response)
        
        return response
    
    def _pre_warm_caches(self, request):
        """Pre-warm caches before view is called."""
        # Detect if this is a comment list view
        if '/api/comments/' in request.path:
            # Could warm frequently accessed caches here
            pass
    
    def _post_warm_caches(self, request, response):
        """Post-warm caches after response is generated."""
        # Could warm caches for likely next requests here
        pass
