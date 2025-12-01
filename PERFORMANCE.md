"""
Template tags for django-comments with caching support.
Load in templates with: {% load comment_tags %}
"""
from django import template
from django.contrib.contenttypes.models import ContentType

from ..cache import get_comment_count_for_object
from ..utils import get_comment_model

register = template.Library()
Comment = get_comment_model()


@register.simple_tag
def get_comment_count(obj, public_only=True):
    """
    Get comment count for an object (uses caching).
    
    Usage in template:
        {% get_comment_count post %}
        {% get_comment_count post public_only=False %}
    """
    try:
        return get_comment_count_for_object(obj, public_only=public_only)
    except Exception:
        return 0


@register.simple_tag
def get_comments_for(obj, public_only=True):
    """
    Get all comments for an object (optimized query).
    
    Usage in template:
        {% get_comments_for post as comments %}
        {% for comment in comments %}
            ...
        {% endfor %}
    """
    try:
        ct = ContentType.objects.get_for_model(obj)
        queryset = Comment.objects.filter(
            content_type=ct,
            object_id=obj.pk
        ).optimized_for_list()
        
        if public_only:
            queryset = queryset.filter(is_public=True, is_removed=False)
        
        return queryset.order_by('-created_at')
    except Exception:
        return Comment.objects.none()


@register.simple_tag
def get_root_comments_for(obj, public_only=True):
    """
    Get root comments (no parent) for an object.
    
    Usage in template:
        {% get_root_comments_for post as root_comments %}
        {% for comment in root_comments %}
            {{ comment.content }}
            {% for child in comment.children.all %}
                {{ child.content }}
            {% endfor %}
        {% endfor %}
    """
    try:
        ct = ContentType.objects.get_for_model(obj)
        queryset = Comment.objects.filter(
            content_type=ct,
            object_id=obj.pk,
            parent__isnull=True
        ).with_full_thread()
        
        if public_only:
            queryset = queryset.filter(is_public=True, is_removed=False)
        
        return queryset.order_by('-created_at')
    except Exception:
        return Comment.objects.none()


@register.filter
def has_comments(obj):
    """
    Check if an object has any comments (uses caching).
    
    Usage in template:
        {% if post|has_comments %}
            <h3>Comments</h3>
        {% endif %}
    """
    try:
        return get_comment_count_for_object(obj, public_only=True) > 0
    except Exception:
        return False


@register.inclusion_tag('django_comments/comment_count.html')
def show_comment_count(obj, link=True):
    """
    Render comment count with optional link.
    
    Usage in template:
        {% show_comment_count post %}
        {% show_comment_count post link=False %}
    
    Requires template: django_comments/comment_count.html
    """
    count = get_comment_count_for_object(obj, public_only=True)
    return {
        'count': count,
        'object': obj,
        'link': link,
    }


@register.inclusion_tag('django_comments/comment_list.html')
def show_comments(obj, max_comments=None):
    """
    Render comment list for an object.
    
    Usage in template:
        {% show_comments post %}
        {% show_comments post max_comments=5 %}
    
    Requires template: django_comments/comment_list.html
    """
    comments = get_comments_for(obj, public_only=True)
    
    if max_comments:
        comments = comments[:max_comments]
    
    return {
        'comments': comments,
        'object': obj,
    }


@register.simple_tag(takes_context=True)
def get_user_comment_count(context, user=None):
    """
    Get comment count for a user (uses current user if not specified).
    
    Usage in template:
        {% get_user_comment_count %}
        {% get_user_comment_count user=some_user %}
    """
    if user is None:
        user = context.get('user')
    
    if not user or user.is_anonymous:
        return 0
    
    try:
        return Comment.objects.filter(user=user).count()
    except Exception:
        return 0