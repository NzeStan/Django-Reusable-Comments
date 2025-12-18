"""
Template tags for django-comments with caching support.
Load in templates with: {% load comment_tags %}
"""
from django import template
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe
from ..cache import get_comment_count_for_object
from ..utils import get_comment_model
from ..formatting import render_comment_content  
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


@register.simple_tag(takes_context=True)
def get_comments_for(context, obj, include_private=False):
    """
    Get all comments for an object.
    
    Args:
        context: Template context (for request.user)
        obj: Object to get comments for
        include_private: If True, use user permissions (default: False, public only)
    
    Usage:
        {% get_comments_for post as comments %}  {# Public only #}
        {% get_comments_for post include_private=True as comments %}  {# Respects permissions #}
    """
    try:
        ct = ContentType.objects.get_for_model(obj)
        queryset = Comment.objects.filter(
            content_type=ct,
            object_id=obj.pk
        ).optimized_for_list()
        
        if include_private:
            # Respect user permissions
            request = context.get('request')
            if request and hasattr(request, 'user'):
                queryset = queryset.visible_to_user(request.user)
            else:
                queryset = queryset.public_only()
        else:
            # Explicitly public only
            queryset = queryset.public_only()
        
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

@register.filter(name='format_comment')
def format_comment(content, format_type=None):
    """
    Format comment content according to COMMENT_FORMAT setting.
    
    Usage in template:
        {{ comment.content|format_comment }}
        {{ comment.content|format_comment:"markdown" }}
    
    Args:
        content: Comment content string
        format_type: Optional format override ('plain', 'markdown', 'html')
    
    Returns:
        Formatted and safe HTML
    
    Examples:
        {# Use default format from settings #}
        <div class="comment-content">
            {{ comment.content|format_comment }}
        </div>
        
        {# Force specific format #}
        <div class="comment-content">
            {{ comment.content|format_comment:"markdown" }}
        </div>
    """
    try:
        return mark_safe(render_comment_content(content, format=format_type))
    except Exception as e:
        # Fallback to raw content with HTML escaped
        from django.utils.html import escape
        import logging
        from ..conf import comments_settings
        
        logger = logging.getLogger(comments_settings.LOGGER_NAME)
        logger.error(f"Failed to format comment content: {e}")
        return mark_safe(escape(content))


@register.filter(name='format_comment_plain')
def format_comment_plain(content):
    """
    Force format comment as plain text (HTML escaped).
    
    Usage in template:
        {{ comment.content|format_comment_plain }}
    """
    return format_comment(content, format_type='plain')


@register.filter(name='format_comment_markdown')
def format_comment_markdown(content):
    """
    Force format comment as Markdown.
    
    Usage in template:
        {{ comment.content|format_comment_markdown }}
    
    Note: Requires markdown package to be installed.
    Falls back to plain text if markdown is not available.
    """
    return format_comment(content, format_type='markdown')


@register.filter(name='format_comment_html')
def format_comment_html(content):
    """
    Force format comment as HTML (sanitized).
    
    Usage in template:
        {{ comment.content|format_comment_html }}
    
    Note: HTML is sanitized to prevent XSS attacks.
    """
    return format_comment(content, format_type='html')


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