from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'django_comments_api'

# Create a router for comment viewsets
router = DefaultRouter()
router.register(r'comments', views.CommentViewSet, basename='comment')

urlpatterns = [
    # Include the router URLs
    path('', include(router.urls)),
    
    # Additional endpoints for specific object comments
    path(
        'content/<str:content_type>/<str:object_id>/comments/',
        views.ContentObjectCommentsViewSet.as_view({'get': 'list'}),
        name='content-object-comments'
    ),
]