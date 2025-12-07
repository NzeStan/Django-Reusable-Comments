"""
Django Reusable Comments
========================

A professional-grade, reusable Django app for adding comment functionality to any model.
"""

__version__ = '0.1.0'

default_app_config = 'django_comments.apps.DjangoCommentsConfig'


# ============================================================================
# EARLY CONFIGURATION FOR SWAPPABLE MODEL
# ============================================================================
# Django's swappable model pattern requires DJANGO_COMMENTS_COMMENT_MODEL
# to be set in settings BEFORE migrations are loaded.
# This code runs on import to ensure it's available early enough.
# ============================================================================

def _setup_swappable_model():
    """
    Ensure DJANGO_COMMENTS_COMMENT_MODEL is set in Django settings.
    
    This runs early (on package import) to support Django's swappable model pattern.
    Migrations need this setting to be available before apps.ready() is called.
    """
    from django.conf import settings
    
    # Only set if not already configured by user
    if not hasattr(settings, 'DJANGO_COMMENTS_COMMENT_MODEL'):
        # Get user settings
        user_config = getattr(settings, 'DJANGO_COMMENTS_CONFIG', {})
        use_uuids = user_config.get('USE_UUIDS', False)
        
        # Set the swappable model setting
        if use_uuids:
            settings.DJANGO_COMMENTS_COMMENT_MODEL = 'django_comments.UUIDComment'
        else:
            settings.DJANGO_COMMENTS_COMMENT_MODEL = 'django_comments.Comment'


# Run setup on import
try:
    _setup_swappable_model()
except Exception:
    # If Django isn't fully configured yet, that's okay
    # This will be set again in apps.py
    pass