from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DjangoCommentsConfig(AppConfig):
    name = 'django_comments'
    verbose_name = _('Comments')
    default_auto_field = 'django.db.models.BigAutoField'
    
    def ready(self):
        """Import signals and configure logging."""
        
        # Import signals to register handlers
        import django_comments.signals
        import django_comments.cache
        
        # Import conf to ensure it's initialized
        from .conf import comments_settings
        
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
        
        logger.info('Django Comments initialized with UUID-based Comment model')