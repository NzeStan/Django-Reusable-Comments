"""
URL configuration for django_comments tests.

Provides comprehensive URL routing for testing all aspects of the comment system:
- Admin interface
- REST API endpoints
- Template views (for integration testing)
- Test model views
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import DetailView, ListView

from .models import TestPost, TestPostWithUUID

# URL patterns for the test suite
urlpatterns = [
    # ========================================================================
    # Admin Interface
    # ========================================================================
    path('admin/', admin.site.urls),
    
    # ========================================================================
    # Django Comments URLs (template-based views)
    # ========================================================================
    path('comments/', include('django_comments.urls', namespace='comments')),
    
    # ========================================================================
    # REST Framework Authentication
    # ========================================================================
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    
    # ========================================================================
    # REST API Endpoints
    # ========================================================================
    path('api/', include('django_comments.api.urls', namespace='django_comments_api')),
    
    # ========================================================================
    # Test Model Views (for integration testing)
    # ========================================================================
    
    # TestPost views (integer PK)
    path('posts/', ListView.as_view(
        model=TestPost,
        template_name='tests/testpost_list.html',
        context_object_name='posts',
        paginate_by=20,
    ), name='testpost_list'),
    
    path('posts/<int:pk>/', DetailView.as_view(
        model=TestPost,
        template_name='tests/testpost_detail.html',
        context_object_name='post',
    ), name='testpost_detail'),
    
    # TestPostWithUUID views (UUID PK)
    path('posts-uuid/', ListView.as_view(
        model=TestPostWithUUID,
        template_name='tests/testpost_list.html',
        context_object_name='posts',
        paginate_by=20,
    ), name='testpost_uuid_list'),
    
    path('posts-uuid/<uuid:pk>/', DetailView.as_view(
        model=TestPostWithUUID,
        template_name='tests/testpost_detail.html',
        context_object_name='post',
    ), name='testpost_uuid_detail'),
]

# Add debug toolbar if in DEBUG mode and installed
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass