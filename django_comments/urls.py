from django.urls import path, include

app_name = 'django_comments'

urlpatterns = [
    path('', include('django_comments.api.urls')),
]