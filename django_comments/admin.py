from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.db.models import Count, Prefetch
from django import forms
from django import VERSION as DJANGO_VERSION
from .models import Comment, CommentFlag, BannedUser, ModerationAction, CommentRevision
from .utils import get_comment_model
from .signals import approve_comment, reject_comment



class CommentAdminForm(forms.ModelForm):
    """
    Custom form for Comment admin.
    """

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
    form = CommentAdminForm
    
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
            'fields': ('user', 'user_name', 'user_email', 'ip_address', 'user_agent')
        }),
        (_('Status'), {
            'fields': ('is_public', 'is_removed', 'created_at', 'updated_at')
        }),
        (_('Flags'), {
            'fields': ('flag_count', 'flags_display')
        }),
    )
    actions = ['approve_comments', 'reject_comments', 'mark_as_removed']
    
    def get_queryset(self, request):
        """
        OPTIMIZED: Prefetch all related data to prevent N+1 queries.
        This is critical for admin list view performance.
        """
        queryset = super().get_queryset(request)
        
        # Select related for foreign keys
        queryset = queryset.select_related(
            'user',
            'content_type',
            'parent',
            'parent__user'
        )
        
        # Prefetch related for many-to-many and reverse foreign keys
        queryset = queryset.prefetch_related(
            Prefetch(
                'flags',
                queryset=CommentFlag.objects.select_related('user')
            )
        )
        
        # Annotate counts to avoid extra queries
        queryset = queryset.annotate(
            flag_count=Count('flags', distinct=True)
        )
        
        return queryset

    def flag_count(self, obj):
        """Display flag count (uses annotated value)."""
        return obj.flag_count
    flag_count.short_description = _('Flags')
    flag_count.admin_order_field = 'flag_count'
    
    def content_snippet(self, obj):
        """Display a snippet of the comment content."""
        if len(obj.content) > 50:
            return f"{obj.content[:50]}..."
        return obj.content
    content_snippet.short_description = _('Content')
    
    def user_info(self, obj):
        """
        Display user information with a safe link to the user's admin change page.
        OPTIMIZED: User is already prefetched via select_related.
        """
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
    user_info.short_description = _('User')
    
    def content_object_link(self, obj):
        """
        Link to the admin change page of the content object.
        OPTIMIZED: content_type is already prefetched.
        """
        try:
            ct = obj.content_type
            model_admin_url = f"admin:{ct.app_label}_{ct.model}_change"
            url = reverse(model_admin_url, args=[obj.object_id])
            return format_html('<a href="{}">{}</a>', url, str(obj.content_object))
        except Exception:
            # Fallback if the reverse fails or object doesn't exist
            return str(obj.content_object) or "(deleted)"
    content_object_link.short_description = _('Content Object')
    
    def flags_display(self, obj):
        """
        Display flags for this comment.
        OPTIMIZED: flags are already prefetched with users.
        """
        # Access prefetched flags (no extra query)
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
    """
    Admin interface for CommentFlag.
    Optimized to work with both Comment types.
    """
    
    list_display = (
        'id',
        'flag',
        'comment_snippet',
        'comment_type_display',
        'user',
        'created_at',
    )
    
    list_filter = (
        'flag',
        'created_at',
        'comment_type',
    )
    
    search_fields = (
        'user__username',
        'user__email',
        'reason',
        'comment_id',
    )
    
    readonly_fields = (
        'comment_type',
        'comment_id',
        'comment_link',
        'created_at',
        'updated_at',
    )
    
    raw_id_fields = ('user',)
    
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Flag Information'), {
            'fields': ('flag', 'reason')
        }),
        (_('Comment'), {
            'fields': ('comment_type', 'comment_id', 'comment_link')
        }),
        (_('User'), {
            'fields': ('user',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'delete_flags_and_comments',
        'delete_flags_only',
    ]
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'user',
            'comment_type'
        )
    
    def comment_type_display(self, obj):
        """Display readable comment type."""
        return f"{obj.comment_type.app_label}.{obj.comment_type.model}"
    comment_type_display.short_description = _('Comment Type')
    
    def comment_snippet(self, obj):
        """
        Display a snippet of the flagged comment.
        Works with both Comment types.
        """
        try:
            comment = obj.comment
            
            if comment:
                content = comment.content
                if len(content) > 50:
                    content = f"{content[:50]}..."
                
                return format_html(
                    '<span title="{}">{}</span>',
                    comment.content,  # Full content in tooltip
                    content  # Truncated for display
                )
            else:
                return format_html(
                    '<span style="color: red;" title="Comment has been deleted">Deleted ({})</span>',
                    obj.comment_id
                )
        except Exception as e:
            return format_html(
                '<span style="color: red;" title="{}">Error loading comment</span>',
                str(e)
            )
    comment_snippet.short_description = _('Comment')
    
    def comment_link(self, obj):
        """
        Provide a link to the flagged comment in admin.
        Works with both Comment types.
        """
        try:
            from django.urls import reverse
            
            # Get comment type info
            app_label = obj.comment_type.app_label
            model = obj.comment_type.model
            
            # Try to build admin URL
            try:
                url = reverse(
                    f'admin:{app_label}_{model}_change',
                    args=[obj.comment_id]
                )
                return format_html(
                    '<a href="{}" target="_blank">View Comment →</a>',
                    url
                )
            except Exception:
                # If reverse fails, just show the ID
                return format_html(
                    'Comment ID: {} (no admin link)',
                    obj.comment_id
                )
        except Exception as e:
            return format_html(
                '<span style="color: red;">Error: {}</span>',
                str(e)
            )
    comment_link.short_description = _('Comment Link')
    
    def delete_flags_and_comments(self, request, queryset):
        """
        Admin action to delete both flags and their associated comments.
        """
        comment_ids_to_delete = {}
        
        # Group comments by type
        for flag in queryset:
            ct = flag.comment_type
            ct_key = f"{ct.app_label}.{ct.model}"
            
            if ct_key not in comment_ids_to_delete:
                comment_ids_to_delete[ct_key] = {
                    'content_type': ct,
                    'ids': []
                }
            
            comment_ids_to_delete[ct_key]['ids'].append(flag.comment_id)
        
        # Delete comments (flags will cascade delete)
        total_deleted = 0
        for ct_key, data in comment_ids_to_delete.items():
            model_class = data['content_type'].model_class()
            if model_class:
                deleted_count = model_class.objects.filter(
                    pk__in=data['ids']
                ).delete()[0]
                total_deleted += deleted_count
        
        self.message_user(
            request,
            _('{count} comments and their flags were deleted.').format(
                count=total_deleted
            )
        )
    delete_flags_and_comments.short_description = _('Delete selected flags AND comments')
    
    def delete_flags_only(self, request, queryset):
        """
        Admin action to delete only the flags (keep comments).
        """
        count = queryset.count()
        queryset.delete()
        
        self.message_user(
            request,
            _('{count} flags were deleted (comments preserved).').format(count=count)
        )
    delete_flags_only.short_description = _('Delete selected flags only')

