from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.db.models import Count
from django import forms

from .models import Comment, CommentFlag
from .utils import get_comment_model, get_model_from_content_type_string
from .signals import approve_comment, reject_comment


class CommentAdminForm(forms.ModelForm):
    """Custom form for Comment admin to handle URLField assume_scheme."""
    
    user_url = forms.URLField(
        required=False,
        assume_scheme='https',
        label=_('User URL')
    )
    
    class Meta:
        model = Comment
        fields = '__all__'


class FlaggedCommentsFilter(admin.SimpleListFilter):
    """
    Custom filter for comments that have been flagged.
    """
    title = _('flags')
    parameter_name = 'flags'

    def lookups(self, request, model_admin):
        return (
            ('flagged', _('Flagged')),
            ('spam', _('Spam')),
            ('offensive', _('Offensive')),
            ('inappropriate', _('Inappropriate')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'flagged':
            return queryset.annotate(flag_count=Count('flags')).filter(flag_count__gt=0)
        elif self.value() in ['spam', 'offensive', 'inappropriate']:
            return queryset.filter(flags__flag=self.value())
        return queryset


class ContentTypeListFilter(admin.SimpleListFilter):
    """
    Custom filter for filtering comments by content type.
    """
    title = _('content type')
    parameter_name = 'content_type'

    def lookups(self, request, model_admin):
        # Get all content types for commented objects
        Comment = get_comment_model()
        content_types = ContentType.objects.filter(
            id__in=Comment.objects.values_list('content_type', flat=True).distinct()
        ).order_by('app_label', 'model')
        
        return [(f"{ct.app_label}.{ct.model}", f"{ct.app_label} | {ct.model}") 
                for ct in content_types]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        
        app_label, model = self.value().split('.')
        return queryset.filter(content_type__app_label=app_label, 
                             content_type__model=model)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    form = CommentAdminForm  # Add this line to use the custom form
    
    list_display = (
        'id', 'content_snippet', 'user_info', 'content_object_link',
        'created_at', 'is_public', 'is_removed', 'flag_count', "parent", 
        "depth", "is_edited", "path", "thread_id", 
    )
    list_filter = (
        'is_public', 'is_removed', 'created_at', 'updated_at',
        FlaggedCommentsFilter, ContentTypeListFilter,
    )
    search_fields = ('content', 'user__username', 'user_name', 'user_email', 'ip_address')
    date_hierarchy = 'created_at'
    raw_id_fields = ('user', 'parent')
    readonly_fields = (
        'content_type', 'object_id', 'content_object_link', 
        'user', 'ip_address', 'user_agent', 'created_at', 'updated_at',
        'flag_count', 'flags_display'
    )
    fieldsets = (
        (_('Comment'), {
            'fields': ('content', 'parent')
        }),
        (_('Content Object'), {
            'fields': ('content_type', 'object_id', 'content_object_link')
        }),
        (_('User Info'), {
            'fields': ('user', 'user_name', 'user_email', 'user_url', 'ip_address', 'user_agent')
        }),
        (_('Status'), {
            'fields': ('is_public', 'is_removed', 'created_at', 'updated_at')
        }),
        (_('Flags'), {
            'fields': ('flag_count', 'flags_display')
        }),
    )
    actions = ['approve_comments', 'reject_comments', 'mark_as_removed']
    

    def flag_count(self, obj):
        return obj.flag_count
    flag_count.short_description = _('Flags')
    flag_count.admin_order_field = 'flag_count'
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            flag_count=Count('flags')
        )
    
    def content_snippet(self, obj):
        """Display a snippet of the comment content."""
        if len(obj.content) > 50:
            return f"{obj.content[:50]}..."
        return obj.content
    content_snippet.short_description = _('Content')
    
    def user_info(self, obj):
        """Display user information with a safe link to the user's admin change page."""
        if obj.user:
            try:
                user_ct = ContentType.objects.get_for_model(obj.user)
                url = reverse(
                    f'admin:{user_ct.app_label}_{user_ct.model}_change',
                    args=[obj.user.pk]
                )
                return format_html('<a href="{}">{}</a>', url, obj.get_user_name())
            except Exception:
                return obj.get_user_name()
        return obj.get_user_name()
    
    def content_object_link(self, obj):
        """Link to the admin change page of the content object."""
        try:
            ct = obj.content_type
            model_admin_url = f"admin:{ct.app_label}_{ct.model}_change"
            url = reverse(model_admin_url, args=[obj.object_id])
            return format_html('<a href="{}">{}</a>', url, str(obj.content_object))
        except Exception:
            # Fallback if the reverse fails or object doesn't exist
            return str(obj.content_object) or "(deleted)"

    
    def flags_display(self, obj):
        """Display flags for this comment."""
        flags = obj.flags.all()
        if not flags:
            return _('No flags')
            
        result = []
        for flag in flags:
            result.append(format_html(
                '{}: {} ({})<br/>',
                flag.get_flag_display(),
                flag.user.get_username(),
                flag.created_at.strftime('%Y-%m-%d %H:%M')
            ))
        return format_html(''.join(result))
    flags_display.short_description = _('Flags')
    
    def approve_comments(self, request, queryset):
        """Admin action to approve selected comments."""
        for comment in queryset:
            approve_comment(comment, moderator=request.user)
        self.message_user(
            request, 
            _("Successfully approved %(count)d comments.") % {'count': queryset.count()}
        )
    approve_comments.short_description = _("Approve selected comments")
    
    def reject_comments(self, request, queryset):
        """Admin action to reject selected comments."""
        for comment in queryset:
            reject_comment(comment, moderator=request.user)
        self.message_user(
            request, 
            _("Successfully rejected %(count)d comments.") % {'count': queryset.count()}
        )
    reject_comments.short_description = _("Reject selected comments")
    
    def mark_as_removed(self, request, queryset):
        """Admin action to mark selected comments as removed."""
        updated = queryset.update(is_removed=True)
        self.message_user(
            request, 
            _("Successfully marked %(count)d comments as removed.") % {'count': updated}
        )
    mark_as_removed.short_description = _("Mark selected comments as removed")


@admin.register(CommentFlag)
class CommentFlagAdmin(admin.ModelAdmin):
    list_display = ('id', 'flag', 'comment_snippet', 'user', 'created_at')
    list_filter = ('flag', 'created_at')
    search_fields = ('comment__content', 'user__username', 'reason')
    date_hierarchy = 'created_at'
    raw_id_fields = ('comment', 'user')
    
    def comment_snippet(self, obj):
        """Display a snippet of the comment content."""
        if len(obj.comment.content) > 50:
            return f"{obj.comment.content[:50]}..."
        return obj.comment.content
    comment_snippet.short_description = _('Comment')