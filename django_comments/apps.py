from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class DjangoCommentsConfig(AppConfig):
    name = 'django_comments'
    verbose_name = _('Comments')
    default_auto_field = 'django.db.models.BigAutoField'
    
    def ready(self):
        """Auto-configure and import signals."""
        
        # Auto-set DJANGO_COMMENTS_COMMENT_MODEL based on USE_UUIDS
        from .conf import comments_settings
        
        if not hasattr(settings, 'DJANGO_COMMENTS_COMMENT_MODEL'):
            # User hasn't explicitly set it, so we set it based on USE_UUIDS
            if comments_settings.USE_UUIDS:
                settings.DJANGO_COMMENTS_COMMENT_MODEL = 'django_comments.UUIDComment'
            else:
                settings.DJANGO_COMMENTS_COMMENT_MODEL = 'django_comments.Comment'
        
        # Import signals to register handlers
        import django_comments.signals
        import django_comments.cache
        
        # Set up logging
        import logging
        logger = logging.getLogger(comments_settings.LOGGER_NAME)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        # Log which model is being used
        model_name = settings.DJANGO_COMMENTS_COMMENT_MODEL
        logger.info(f'Django Comments initialized using model: {model_name}')