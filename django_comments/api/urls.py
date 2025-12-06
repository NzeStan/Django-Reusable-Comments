from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'django_comments_api'

# Create a router for comment viewsets
router = DefaultRouter()
router.register(r'comments', views.CommentViewSet, basename='comment')

# NEW: Register flag and banned user viewsets
router.register(r'flags', views.FlagViewSet, basename='flag')
router.register(r'banned-users', views.BannedUserViewSet, basename='banned-user')

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
