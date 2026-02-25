from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.db.models import Count, Q
from django import forms
from django.utils import timezone
from .models import (
    Comment, 
    CommentFlag, 
    BannedUser, 
    ModerationAction, 
    CommentRevision
)
from .utils import get_comment_model
from django_comments.signals import approve_comment, reject_comment
from .notifications import notify_user_unbanned


# ============================================================================
# CUSTOM FILTERS
# ============================================================================

class FlaggedCommentsFilter(admin.SimpleListFilter):
    """Custom filter for comments that have been flagged."""
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
    """Custom filter for filtering comments by content type."""
    title = _('content type')
    parameter_name = 'content_type'

    def lookups(self, request, model_admin):
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
        return queryset.filter(
            content_type__app_label=app_label, 
            content_type__model=model
        )


class BanStatusFilter(admin.SimpleListFilter):
    """Custom filter for ban status."""
    title = _('ban status')
    parameter_name = 'ban_status'

    def lookups(self, request, model_admin):
        return (
            ('active', _('Active')),
            ('expired', _('Expired')),
            ('permanent', _('Permanent')),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        
        if self.value() == 'active':
            return queryset.filter(
                Q(banned_until__isnull=True) | Q(banned_until__gt=now)
            )
        elif self.value() == 'expired':
            return queryset.filter(
                banned_until__isnull=False,
                banned_until__lte=now
            )
        elif self.value() == 'permanent':
            return queryset.filter(banned_until__isnull=True)
        
        return queryset


class CommentDepthFilter(admin.SimpleListFilter):
    """Filter comments by depth in thread."""
    title = _('thread depth')
    parameter_name = 'depth'

    def lookups(self, request, model_admin):
        return (
            ('0', _('Root comments')),
            ('1', _('Direct replies')),
            ('2+', _('Nested replies')),
        )

    def queryset(self, request, queryset):
        if self.value() == '0':
            return queryset.filter(parent__isnull=True)
        elif self.value() == '1':
            return queryset.filter(parent__isnull=False, parent__parent__isnull=True)
        elif self.value() == '2+':
            return queryset.filter(parent__parent__isnull=False)
        return queryset


# ============================================================================
# FORMS
# ============================================================================

class CommentAdminForm(forms.ModelForm):
    """Custom form for Comment admin."""

    class Meta:
        model = Comment
        fields = '__all__'


# ============================================================================
# ADMIN CLASSES
# ============================================================================

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """
    FIXED: Optimized admin interface for Comment model.
    
    Main fix: get_queryset() now uses the fixed optimized_for_list() method
    which properly handles UUID to string conversion for flag counts.
    """
    
    list_display = (
        'id', 
        'content_snippet', 
        'user_info', 
        'content_object_link',
        'created_at', 
        'is_public', 
        'is_removed', 
        'flag_count',  # This now works correctly!
        'parent', 
        'depth_display', 
        'is_edited',
    )
    
    list_filter = (
        'is_public', 
        'is_removed', 
        'created_at', 
        'updated_at',
        # Note: Add your custom filters here if you have them
        # FlaggedCommentsFilter, ContentTypeListFilter, CommentDepthFilter,
    )
    
    search_fields = (
        'content', 
        'user__username', 
        'user__email',
        'user_name', 
        'user_email', 
        'ip_address',
        'id',
    )
    
    date_hierarchy = 'created_at'
    
    raw_id_fields = ('user', 'parent')
    
    readonly_fields = (
        'content_type', 
        'object_id', 
        'content_object_link', 
        'user', 
        'ip_address', 
        'user_agent', 
        'created_at', 
        'updated_at',
        'flag_count', 
        'flags_display',
        'thread_id',
        'path',
        'depth_display',
        'edit_history_link',
        'moderation_history_link',
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
        (_('Threading'), {
            'fields': ('thread_id', 'path', 'depth_display'),
            'classes': ('collapse',)
        }),
        (_('Flags'), {
            'fields': ('flag_count', 'flags_display')
        }),
        (_('History'), {
            'fields': ('edit_history_link', 'moderation_history_link'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'approve_comments', 
        'reject_comments', 
        'mark_as_removed',
        'mark_as_not_removed',
    ]
    
    def get_queryset(self, request):
        """
        FIXED: Use the corrected optimized_for_list() method.
        
        This automatically includes the fixed flags_count_annotated
        annotation that properly handles UUID to string conversion.
        """
        # Use the FIXED optimized_for_list() method from managers.py
        return Comment.objects.optimized_for_list()

    def flag_count(self, obj):
        """
        FIXED: Display flag count using the corrected annotation.
        
        Now properly reads from flags_count_annotated which uses
        Subquery with UUID-to-string casting.
        """
        # The annotation now works correctly!
        count = getattr(obj, 'flags_count_annotated', None)
        
        # Fallback to counting flags directly if annotation missing
        if count is None:
            count = obj.flags.count()
        
        if count > 0:
            url = reverse('admin:django_comments_commentflag_changelist')
            # Filter by comment_id (string representation of UUID)
            return format_html(
                '<a href="{}?comment_id={}" style="color: #ba2121; font-weight: bold;">{}</a>',
                url, str(obj.pk), count
            )
        return count
    
    flag_count.short_description = _('Flags')
    flag_count.admin_order_field = 'flags_count_annotated'
    
    def content_snippet(self, obj):
        """Display a snippet of the comment content."""
        max_length = 60
        if len(obj.content) > max_length:
            return format_html(
                '<span title="{}">{}&hellip;</span>',
                obj.content,
                obj.content[:max_length]
            )
        return obj.content
    content_snippet.short_description = _('Content')
    
    def user_info(self, obj):
        """Display user information with link to user admin."""
        if obj.user:
            try:
                user_ct = ContentType.objects.get_for_model(obj.user)
                url = reverse(
                    f'admin:{user_ct.app_label}_{user_ct.model}_change',
                    args=[obj.user.pk]
                )
                return format_html(
                    '<a href="{}">{}</a>',
                    url,
                    obj.get_user_name()
                )
            except Exception:
                return obj.get_user_name()
        return format_html(
            '<span style="color: #999;">{}</span>',
            obj.get_user_name()
        )
    user_info.short_description = _('User')
    
    def content_object_link(self, obj):
        """Link to the admin change page of the content object."""
        try:
            ct = obj.content_type
            model_admin_url = f"admin:{ct.app_label}_{ct.model}_change"
            url = reverse(model_admin_url, args=[obj.object_id])
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                url,
                str(obj.content_object) or "(object)"
            )
        except Exception:
            return format_html(
                '<span style="color: #999;">{}</span>',
                str(obj.content_object) or "(deleted)"
            )
    content_object_link.short_description = _('Content Object')
    
    def flags_display(self, obj):
        """
        FIXED: Display flags for this comment.
        Now properly fetches flags using the prefetched data.
        """
        # Flags are already prefetched in get_queryset()
        flags = obj.flags.all()
        
        if not flags:
            return format_html('<span style="color: #999;">No flags</span>')
            
        result = []
        for flag in flags:
            style = 'color: #ba2121;' if flag.flag == 'spam' else ''
            result.append(format_html(
                '<div style="{}"><strong>{}:</strong> {} ({})</div>',
                style,
                flag.get_flag_display(),
                flag.user.get_username() if flag.user else 'Unknown',
                flag.created_at.strftime('%Y-%m-%d %H:%M')
            ))
        return format_html(''.join(result))
    flags_display.short_description = _('Flags')
    
    def depth_display(self, obj):
        """Display comment depth in thread."""
        depth = obj.depth
        if depth == 0:
            return mark_safe('<span style="color: #417690; font-weight: bold;">Root</span>')
        return format_html('{}{}', '↳ ' * depth, depth)
    depth_display.short_description = _('Depth')
    
    def edit_history_link(self, obj):
        """Link to edit history."""
        url = reverse('admin:django_comments_commentrevision_changelist')
        count = CommentRevision.objects.filter(
            comment_type=obj.content_type,
            comment_id=str(obj.pk)  # Convert UUID to string
        ).count()
        
        if count > 0:
            return format_html(
                '<a href="{}?comment_id={}">{} revision(s)</a>',
                url, str(obj.pk), count
            )
        return format_html('<span style="color: #999;">No revisions</span>')
    edit_history_link.short_description = _('Edit History')
    
    def moderation_history_link(self, obj):
        """Link to moderation history."""
        url = reverse('admin:django_comments_moderationaction_changelist')
        count = ModerationAction.objects.filter(
            comment_type=obj.content_type,
            comment_id=str(obj.pk)  # Convert UUID to string
        ).count()
        
        if count > 0:
            return format_html(
                '<a href="{}?comment_id={}">{} action(s)</a>',
                url, str(obj.pk), count
            )
        return format_html('<span style="color: #999;">No actions</span>')
    moderation_history_link.short_description = _('Moderation History')
    
    # Admin actions
    def approve_comments(self, request, queryset):
        """
        Approve selected comments.
        Calls approve_comment() for each comment to trigger signals and logging.
        """
        count = 0
        for comment in queryset:
            try:
                approve_comment(comment, moderator=request.user)
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    _("Error approving comment %(id)s: %(error)s") % {
                        'id': comment.pk,
                        'error': str(e)
                    },
                    level='error'
                )
        
        if count > 0:
            self.message_user(
                request, 
                _("Successfully approved %(count)d comment(s).") % {'count': count}
            )
    approve_comments.short_description = _("Approve selected comments")
    
    def reject_comments(self, request, queryset):
        """
        Reject selected comments.
        Calls reject_comment() for each comment to trigger signals and logging.
        """
        count = 0
        for comment in queryset:
            try:
                reject_comment(comment, moderator=request.user)
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    _("Error rejecting comment %(id)s: %(error)s") % {
                        'id': comment.pk,
                        'error': str(e)
                    },
                    level='error'
                )
        
        if count > 0:
            self.message_user(
                request, 
                _("Successfully rejected %(count)d comment(s).") % {'count': count}
            )
    reject_comments.short_description = _("Reject selected comments")

    
    def mark_as_removed(self, request, queryset):
        """Mark selected comments as removed."""
        updated = queryset.update(is_removed=True)
        self.message_user(
            request, 
            _("Successfully marked %(count)d comment(s) as removed.") % {'count': updated}
        )
    mark_as_removed.short_description = _("Mark as removed")
    
    def mark_as_not_removed(self, request, queryset):
        """Restore removed comments."""
        updated = queryset.update(is_removed=False)
        self.message_user(
            request, 
            _("Successfully restored %(count)d comment(s).") % {'count': updated}
        )
    mark_as_not_removed.short_description = _("Restore removed comments")

@admin.register(CommentFlag)
class CommentFlagAdmin(admin.ModelAdmin):
    """
    Optimized admin interface for CommentFlag.
    Works with UUID-based Comment model.
    """
    
    list_display = (
        'id',
        'flag_display',
        'comment_snippet',
        'comment_type_display',
        'user',
        'created_at',
        'reviewed',
        'reviewed_by',
    )
    
    list_filter = (
        'flag',
        'reviewed',
        'created_at',
        'comment_type',
        'review_action',
    )
    
    search_fields = (
        'user__username',
        'user__email',
        'reason',
        'comment_id',
        'reviewed_by__username',
    )
    
    readonly_fields = (
        'comment_type',
        'comment_id',
        'comment_link',
        'user',
        'created_at',
        'updated_at',
    )
    
    raw_id_fields = ('user', 'reviewed_by')
    
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
        (_('Review'), {
            'fields': ('reviewed', 'reviewed_by', 'reviewed_at', 'review_action', 'review_notes')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'mark_as_reviewed_dismissed',
        'mark_as_reviewed_actioned',
        'delete_flags_and_comments',
        'delete_flags_only',
    ]
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'user',
            'comment_type',
            'reviewed_by',
        )
    
    def flag_display(self, obj):
        """Display flag type with color."""
        colors = {
            'spam': '#ba2121',
            'harassment': '#ba2121',
            'hate_speech': '#ba2121',
            'violence': '#ba2121',
            'sexual': '#efb80b',
            'misinformation': '#efb80b',
            'offensive': '#417690',
            'inappropriate': '#417690',
            'off_topic': '#999',
            'other': '#999',
        }
        color = colors.get(obj.flag, '#666')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_flag_display()
        )
    flag_display.short_description = _('Flag')
    flag_display.admin_order_field = 'flag'
    
    def comment_type_display(self, obj):
        """Display readable comment type."""
        return f"{obj.comment_type.app_label}.{obj.comment_type.model}"
    comment_type_display.short_description = _('Comment Type')
    
    def comment_snippet(self, obj):
        """
        Display a snippet of the flagged comment.
        Handles deleted comments gracefully.
        """
        try:
            comment = obj.comment
            
            if comment:
                content = comment.content
                max_length = 50
                
                if len(content) > max_length:
                    content = f"{content[:max_length]}&hellip;"
                
                return format_html(
                    '<span title="{}">{}</span>',
                    comment.content,
                    content
                )
            else:
                return format_html(
                    '<span style="color: #ba2121;" title="Comment has been deleted">Deleted ({})</span>',
                    obj.comment_id
                )
        except Exception as e:
            return format_html(
                '<span style="color: #ba2121;" title="{}">Error</span>',
                str(e)
            )
    comment_snippet.short_description = _('Comment')
    
    def comment_link(self, obj):
        """
        Provide a link to the flagged comment in admin.
        """
        try:
            app_label = obj.comment_type.app_label
            model = obj.comment_type.model
            
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
                return format_html(
                    'Comment ID: {} <span style="color: #999;">(no admin link)</span>',
                    obj.comment_id
                )
        except Exception as e:
            return format_html(
                '<span style="color: #ba2121;">Error: {}</span>',
                str(e)
            )
    comment_link.short_description = _('Comment Link')
    
    def mark_as_reviewed_dismissed(self, request, queryset):
        """Mark flags as reviewed and dismissed."""
        count = 0
        for flag in queryset.filter(reviewed=False):
            flag.mark_reviewed(
                moderator=request.user,
                action='dismissed',
                notes='Bulk dismissed by moderator'
            )
            count += 1
        
        self.message_user(
            request,
            _('{count} flag(s) marked as reviewed (dismissed).').format(count=count)
        )
    mark_as_reviewed_dismissed.short_description = _('Mark as reviewed (dismissed)')
    
    def mark_as_reviewed_actioned(self, request, queryset):
        """Mark flags as reviewed and actioned."""
        count = 0
        for flag in queryset.filter(reviewed=False):
            flag.mark_reviewed(
                moderator=request.user,
                action='actioned',
                notes='Bulk actioned by moderator'
            )
            count += 1
        
        self.message_user(
            request,
            _('{count} flag(s) marked as reviewed (actioned).').format(count=count)
        )
    mark_as_reviewed_actioned.short_description = _('Mark as reviewed (actioned)')
    
    def delete_flags_and_comments(self, request, queryset):
        """Admin action to delete both flags and their associated comments."""
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
            _('{count} comment(s) and their flags were deleted.').format(
                count=total_deleted
            )
        )
    delete_flags_and_comments.short_description = _('Delete selected flags AND comments')
    
    def delete_flags_only(self, request, queryset):
        """Admin action to delete only the flags (keep comments)."""
        count = queryset.count()
        queryset.delete()
        
        self.message_user(
            request,
            _('{count} flag(s) were deleted (comments preserved).').format(count=count)
        )
    delete_flags_only.short_description = _('Delete selected flags only')


@admin.register(BannedUser)
class BannedUserAdmin(admin.ModelAdmin):
    """
    Optimized admin interface for BannedUser model.
    """
    
    list_display = (
        'id',
        'user_link',
        'ban_status_display',
        'banned_until',
        'reason_snippet',
        'banned_by',
        'created_at',
    )
    
    list_filter = (
        BanStatusFilter,
        'created_at',
        'updated_at',
    )
    
    search_fields = (
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'reason',
        'banned_by__username',
    )
    
    date_hierarchy = 'created_at'
    
    raw_id_fields = ('user', 'banned_by')
    
    readonly_fields = (
        'created_at',
        'updated_at',
        'is_active',
        'days_remaining',
        'user_comment_count',
    )
    
    fieldsets = (
        (_('User'), {
            'fields': ('user', 'user_comment_count')
        }),
        (_('Ban Details'), {
            'fields': ('banned_until', 'reason', 'is_active', 'days_remaining')
        }),
        (_('Metadata'), {
            'fields': ('banned_by', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['unban_users', 'extend_ban', 'make_permanent']
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'user',
            'banned_by',
        )
    
    def user_link(self, obj):
        """Link to user admin page."""
        try:
            user_ct = ContentType.objects.get_for_model(obj.user)
            url = reverse(
                f'admin:{user_ct.app_label}_{user_ct.model}_change',
                args=[obj.user.pk]
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.user.get_username()
            )
        except Exception:
            return obj.user.get_username()
    user_link.short_description = _('User')
    
    def ban_status_display(self, obj):
        """Display ban status with color coding."""
        if obj.is_active:
            if obj.banned_until:
                return format_html(
                    '<span style="background: #ffc107; color: #000; padding: 3px 8px; border-radius: 3px; font-weight: bold;">Temporary</span>'
                )
            else:
                return format_html(
                    '<span style="background: #dc3545; color: #fff; padding: 3px 8px; border-radius: 3px; font-weight: bold;">Permanent</span>'
                )
        else:
            return format_html(
                '<span style="background: #28a745; color: #fff; padding: 3px 8px; border-radius: 3px;">Expired</span>'
            )
    ban_status_display.short_description = _('Status')
    
    def reason_snippet(self, obj):
        """Display reason snippet with tooltip."""
        max_length = 50
        if len(obj.reason) > max_length:
            return format_html(
                '<span title="{}">{}&hellip;</span>',
                obj.reason,
                obj.reason[:max_length]
            )
        return obj.reason
    reason_snippet.short_description = _('Reason')
    
    def days_remaining(self, obj):
        """Display days remaining in ban."""
        if not obj.banned_until:
            return format_html('<span style="color: #ba2121; font-weight: bold;">Permanent</span>')
        
        if not obj.is_active:
            return format_html('<span style="color: #999;">Expired</span>')
        
        days = (obj.banned_until - timezone.now()).days
        if days < 0:
            return format_html('<span style="color: #999;">Expired</span>')
        elif days == 0:
            return format_html('<span style="color: #efb80b; font-weight: bold;">Today</span>')
        elif days <= 7:
            return format_html('<span style="color: #efb80b;">{} days</span>', days)
        else:
            return format_html('<span>{} days</span>', days)
    days_remaining.short_description = _('Days Remaining')
    
    def user_comment_count(self, obj):
        """Display total comment count for this user."""
        count = Comment.objects.filter(user=obj.user).count()
        if count > 0:
            url = reverse('admin:django_comments_comment_changelist')
            return format_html(
                '<a href="{}?user={}">{} comment(s)</a>',
                url, obj.user.pk, count
            )
        return '0 comments'
    user_comment_count.short_description = _('User Comments')
    
    def unban_users(self, request, queryset):
        """Admin action to unban users."""
        count = 0
        for ban in queryset:
            if ban.is_active:
                user = ban.user
                original_reason = ban.reason
                ban.delete()
                
                # Send notification
                try:
                    notify_user_unbanned(
                        user=user,
                        unbanned_by=request.user,
                        original_ban_reason=original_reason
                    )
                except Exception:
                    pass
                
                count += 1
        
        self.message_user(
            request,
            _('Successfully unbanned {count} user(s).').format(count=count)
        )
    unban_users.short_description = _('Unban selected users')
    
    def extend_ban(self, request, queryset):
        """Extend ban by 30 days."""
        from datetime import timedelta
        count = 0
        
        for ban in queryset.filter(banned_until__isnull=False):
            if ban.is_active:
                ban.banned_until = ban.banned_until + timedelta(days=30)
                ban.save()
                count += 1
        
        self.message_user(
            request,
            _('Extended {count} ban(s) by 30 days.').format(count=count)
        )
    extend_ban.short_description = _('Extend temporary bans by 30 days')
    
    def make_permanent(self, request, queryset):
        """Make temporary bans permanent."""
        count = queryset.filter(
            banned_until__isnull=False
        ).update(banned_until=None)
        
        self.message_user(
            request,
            _('Made {count} ban(s) permanent.').format(count=count)
        )
    make_permanent.short_description = _('Make selected bans permanent')


@admin.register(CommentRevision)
class CommentRevisionAdmin(admin.ModelAdmin):
    """
    Admin interface for CommentRevision (read-only audit log).
    """
    
    list_display = (
        'id',
        'comment_link',
        'content_snippet',
        'edited_by',
        'edited_at',
        'was_public',
        'was_removed',
    )
    
    list_filter = (
        'edited_at',
        'was_public',
        'was_removed',
        'comment_type',
    )
    
    search_fields = (
        'comment_id',
        'content',
        'edited_by__username',
    )
    
    date_hierarchy = 'edited_at'
    
    raw_id_fields = ('edited_by',)
    
    readonly_fields = (
        'comment_type',
        'comment_id',
        'comment_link',
        'content',
        'edited_by',
        'edited_at',
        'was_public',
        'was_removed',
    )
    
    fieldsets = (
        (_('Comment'), {
            'fields': ('comment_type', 'comment_id', 'comment_link')
        }),
        (_('Revision'), {
            'fields': ('content', 'edited_by', 'edited_at')
        }),
        (_('State at Edit Time'), {
            'fields': ('was_public', 'was_removed')
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'edited_by',
            'comment_type',
        )
    
    def has_add_permission(self, request):
        """Revisions are created automatically, not manually."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion of revision history if needed."""
        return request.user.is_superuser
    
    def content_snippet(self, obj):
        """Display content snippet with tooltip."""
        max_length = 60
        if len(obj.content) > max_length:
            return format_html(
                '<span title="{}">{}&hellip;</span>',
                obj.content,
                obj.content[:max_length]
            )
        return obj.content
    content_snippet.short_description = _('Content')
    
    def comment_link(self, obj):
        """Link to the comment."""
        try:
            url = reverse(
                f'admin:{obj.comment_type.app_label}_{obj.comment_type.model}_change',
                args=[obj.comment_id]
            )
            return format_html(
                '<a href="{}" target="_blank">View Comment →</a>',
                url
            )
        except Exception:
            return format_html(
                'Comment ID: {} <span style="color: #999;">(no link)</span>',
                obj.comment_id
            )
    comment_link.short_description = _('Comment')


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    """
    Admin interface for ModerationAction (read-only audit log).
    """
    
    list_display = (
        'id',
        'action_display',
        'comment_link',
        'moderator',
        'affected_user',
        'timestamp',
        'reason_snippet',
    )
    
    list_filter = (
        'action',
        'timestamp',
        'comment_type',
    )
    
    search_fields = (
        'comment_id',
        'reason',
        'moderator__username',
        'affected_user__username',
        'ip_address',
    )
    
    date_hierarchy = 'timestamp'
    
    raw_id_fields = ('moderator', 'affected_user')
    
    readonly_fields = (
        'comment_type',
        'comment_id',
        'comment_link',
        'moderator',
        'action',
        'reason',
        'affected_user',
        'timestamp',
        'ip_address',
    )
    
    fieldsets = (
        (_('Action'), {
            'fields': ('action', 'reason')
        }),
        (_('Comment'), {
            'fields': ('comment_type', 'comment_id', 'comment_link')
        }),
        (_('Users'), {
            'fields': ('moderator', 'affected_user')
        }),
        (_('Metadata'), {
            'fields': ('timestamp', 'ip_address')
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'moderator',
            'affected_user',
            'comment_type',
        )
    
    def has_add_permission(self, request):
        """Actions are logged automatically, not created manually."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete audit logs."""
        return request.user.is_superuser
    
    def action_display(self, obj):
        """Display action with color coding."""
        colors = {
            'approved': '#28a745',
            'rejected': '#dc3545',
            'deleted': '#ba2121',
            'edited': '#417690',
            'flagged': '#ffc107',
            'unflagged': '#999',
            'banned_user': '#dc3545',
            'unbanned_user': '#28a745',
        }
        color = colors.get(obj.action, '#666')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_action_display()
        )
    action_display.short_description = _('Action')
    action_display.admin_order_field = 'action'
    
    def comment_link(self, obj):
        """Link to the comment if it exists."""
        if not obj.comment_id:
            return format_html('<span style="color: #999;">N/A (user action)</span>')
        
        try:
            url = reverse(
                f'admin:{obj.comment_type.app_label}_{obj.comment_type.model}_change',
                args=[obj.comment_id]
            )
            return format_html(
                '<a href="{}" target="_blank">View Comment →</a>',
                url
            )
        except Exception:
            return format_html(
                'Comment ID: {} <span style="color: #999;">(deleted)</span>',
                obj.comment_id
            )
    comment_link.short_description = _('Comment')
    
    def reason_snippet(self, obj):
        """Display reason snippet with tooltip."""
        if not obj.reason:
            return format_html('<span style="color: #999;">—</span>')
        
        max_length = 50
        if len(obj.reason) > max_length:
            return format_html(
                '<span title="{}">{}&hellip;</span>',
                obj.reason,
                obj.reason[:max_length]
            )
        return obj.reason
    reason_snippet.short_description = _('Reason')