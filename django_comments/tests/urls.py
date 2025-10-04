"""
URL configuration for tests.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import DetailView, ListView

from .models import TestPost

urlpatterns = [
    path('admin/', admin.site.urls),
    path('comments/', include('django_comments.urls')),
    path('api-auth/', include('rest_framework.urls')),
    
    path('api/', include('django_comments.api.urls', namespace='api')),
    
    # Test URLs for TestPost model
    path('posts/', ListView.as_view(
        model=TestPost,
        template_name='test_post_list.html'
    ), name='test_post_list'),
    
    path('posts/<int:pk>/', DetailView.as_view(
        model=TestPost,
        template_name='test_post_detail.html'
    ), name='test_post_detail'),
]