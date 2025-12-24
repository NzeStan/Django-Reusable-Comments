from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'django_comments_api'

router = DefaultRouter()
router.register(r'comments', views.CommentViewSet, basename='comment')
router.register(r'flags', views.FlagViewSet, basename='flag')
router.register(r'banned-users', views.BannedUserViewSet, basename='banned-user')

urlpatterns = [
    path('', include(router.urls)),

    # NO “content/” prefix here – root urlconf already gives /api/content/
    path(
        '<str:app_label>/<str:model>/<str:object_id>/comments/',
        views.ContentObjectCommentsViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='content-object-comments'
    ),
]