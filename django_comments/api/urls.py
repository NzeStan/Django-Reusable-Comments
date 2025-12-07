from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'django_comments_api'

# Create router and register viewsets
router = DefaultRouter()
router.register(r'comments', views.CommentViewSet, basename='comment')
router.register(r'flags', views.FlagViewSet, basename='flag')
router.register(r'banned-users', views.BannedUserViewSet, basename='banned-user')

urlpatterns = [
    path('', include(router.urls)),
    
    # Additional custom endpoint for getting comments by content object
    # GET /content/{content_type}/{object_id}/comments/
    path(
        'content/<str:content_type>/<str:object_id>/comments/',
        views.ContentObjectCommentsViewSet.as_view({'get': 'list'}),
        name='content-object-comments'
    ),
]