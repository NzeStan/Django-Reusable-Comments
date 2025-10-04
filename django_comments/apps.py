from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DjangoCommentsConfig(AppConfig):
    name = 'django_comments'
    verbose_name = _('Comments')
    default_auto_field = 'django.db.models.BigAutoField'
    
    def ready(self):
        """
        Import signals to register signal handlers.
        """
        import django_comments.signals
        
        # Set up logging
        import logging
        from .conf import comments_settings
        
        logger = logging.getLogger(comments_settings.LOGGER_NAME)
        if not logger.handlers:
            # Only add handler if none exist
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        # Log that the app is ready
        logger.info('Django Comments app initialized')