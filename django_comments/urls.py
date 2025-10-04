from django.urls import path, include

app_name = 'django_comments'

urlpatterns = [
    # REST API URLs
    path('api/', include('django_comments.api.urls', namespace='api')),
]