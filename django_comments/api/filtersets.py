import django_filters
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from ..utils import get_comment_model

Comment = get_comment_model()


class ContentTypeFilter(django_filters.CharFilter):
    """
    Custom filter for filtering by content type string (app_label.model_name).
    """
    def filter(self, qs, value):
        if not value:
            return qs
        
        try:
            app_label, model = value.split('.')
            content_type = ContentType.objects.get(
                app_label=app_label,
                model=model
            )
            return qs.filter(content_type=content_type)
        except (ValueError, ContentType.DoesNotExist):
            return qs.none()


class CommentFilterSet(django_filters.FilterSet):
    """
    FilterSet for comments API.
    """
    # Content type filtering (app_label.model_name)
    content_type = ContentTypeFilter(
        help_text=_("Filter by content type (e.g., 'blog.post')")
    )
    
    # Object ID filtering
    object_id = django_filters.CharFilter(
        help_text=_("Filter by object ID")
    )
    
    # User filtering by user ID
    user = django_filters.CharFilter(  
        help_text=_("Filter by user ID")
    )
    
    # Date range filtering
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text=_("Filter comments created after this date/time")
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text=_("Filter comments created before this date/time")
    )
    
    # Status filtering
    is_public = django_filters.BooleanFilter(
        help_text=_("Filter by public status")
    )
    is_removed = django_filters.BooleanFilter(
        help_text=_("Filter by removed status")
    )
    
    # Thread filtering
    thread_id = django_filters.CharFilter(
        help_text=_("Filter by thread ID")
    )
    parent = django_filters.CharFilter(
        help_text=_("Filter by parent comment ID"),
        method='filter_parent'
    )
    is_root = django_filters.BooleanFilter(
        help_text=_("Filter for root comments (no parent)"),
        method='filter_is_root'
    )
    
    class Meta:
        model = Comment
        fields = [
            'content_type', 'object_id', 'user', 
            'created_after', 'created_before',
            'is_public', 'is_removed', 'thread_id'
        ]
    
    def filter_parent(self, queryset, name, value):
        """
        Filter by parent ID.
        If value is 'none', return comments with no parent.
        """
        if value == 'none':
            return queryset.filter(parent__isnull=True)
        return queryset.filter(parent=value)
    
    def filter_is_root(self, queryset, name, value):
        """
        Filter for root comments (no parent).
        """
        if value:
            return queryset.filter(parent__isnull=True)
        return queryset.filter(parent__isnull=False)