from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _
import logging


class DjangoCommentsConfig(AppConfig):
    name = 'django_comments'
    verbose_name = _('Comments')
    default_auto_field = 'django.db.models.BigAutoField'
    
    def ready(self):
    
        # Import signals to register handlers and cache module to ensure it's loaded
        import django_comments.signals  
        import django_comments.cache    

        # Ensure comments settings are imported/initialized
        from .conf import comments_settings  

        logger = logging.getLogger(comments_settings.LOGGER_NAME)
        logger.info('Django Comments initialized with UUID-based Comment model')
