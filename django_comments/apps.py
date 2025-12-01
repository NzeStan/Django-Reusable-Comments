# django_comments/apps.py
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
        import django_comments.cache  # Add this line to connect cache signals
        
        # Set up logging
        import logging
        from .conf import comments_settings
        
        logger = logging.getLogger(comments_settings.LOGGER_NAME)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        logger.info('Django Comments app initialized with performance optimizations')