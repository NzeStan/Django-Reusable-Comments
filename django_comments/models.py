from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid
import logging

from .conf import comments_settings
from .managers import CommentManager, CommentQuerySet, CommentFlagManager

logger = logging.getLogger(comments_settings.LOGGER_NAME)


class AbstractCommentBase(models.Model):
    """Base class with timestamp fields."""
    created_at = models.DateTimeField(_('Created at'), default=timezone.now)
    updated_at = models.DateTimeField(_('Updated at'), auto_now=True)
    
    class Meta:
        abstract = True


class BaseCommentMixin(models.Model):
    """
    All comment fields and methods.
    """
    
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name=_('Content type'),
        related_name='%(app_label)s_%(class)s_comments'
    )
    
    object_id = models.CharField(
        _('Object ID'),
        max_length=255,
        db_index=True
    )
    content_object = GenericForeignKey('content_type', 'object_id')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_comments',
        verbose_name=_('User')
    )
    
    user_name = models.CharField(_('User name'), max_length=100, blank=True)
    user_email = models.EmailField(_('User email'), blank=True)
    ip_address = models.GenericIPAddressField(_('IP address'), blank=True, null=True)
    user_agent = models.TextField(_('User agent'), blank=True)
    content = models.TextField(_('Content'))
    is_public = models.BooleanField(
        _('Is public'),
        default=True,
        help_text=_('Uncheck this box to hide the comment from public view.')
    )
    is_removed = models.BooleanField(
        _('Is removed'),
        default=False,
        help_text=_('Check this box if the comment should be treated as removed.')
    )
    path = models.CharField(
        _('Materialized path'),
        max_length=255,
        blank=True,
        db_index=True,
        help_text=_('Used for storing hierarchical comment structure')
    )
    thread_id = models.CharField(
        _('Thread ID'),
        max_length=255,
        blank=True,
        db_index=True
    )
    
    class Meta:
        abstract = True
    
    def __str__(self):
        return _("Comment by {user} on {object}").format(
            user=self.get_user_name(),
            object=str(self.content_object)
        )
    
    def clean(self):
        """
        Validate comment before saving.
        Catches errors early before database operations.
        """
        super().clean()
        
        if not self.content or not self.content.strip():
            raise ValidationError({
                'content': _('Comment content cannot be empty or contain only whitespace.')
            })
        
        from django.conf import settings as django_settings
        django_comments_config = getattr(django_settings, 'DJANGO_COMMENTS', {})
        max_length = django_comments_config.get('MAX_COMMENT_LENGTH', comments_settings.MAX_COMMENT_LENGTH)
        
        if max_length and len(self.content) > max_length:
            raise ValidationError({
                'content': _(f'Comment exceeds maximum length of {max_length} characters.')
            })
        if not self.user and not self.user_name and not self.user_email:
            raise ValidationError({
                'user_name': _('Anonymous comments must provide either a name or email address.')
            })
        
        if self.parent and self._state.adding:
            self._validate_parent()
    
    def _validate_parent(self):
        """Validate parent comment state."""
        if not self.parent.pk:
            raise ValidationError({
                'parent': _("Parent comment must be saved before adding children.")
            })
        
        # Ensure parent has required threading fields
        if not self.parent.path or not self.parent.thread_id:
            # Try refreshing from database
            try:
                self.parent.refresh_from_db(fields=['path', 'thread_id'])
            except Exception as e:
                logger.error(f"Could not refresh parent comment {self.parent.pk}: {e}")
            
            # Check again
            if not self.parent.path or not self.parent.thread_id:
                raise ValidationError({
                    'parent': _(
                        f"Parent comment {self.parent.pk} is missing threading data. "
                        "Database may be in inconsistent state."
                    )
                })
        
        # Check maximum depth - reload settings each time for test override support
        from django.conf import settings as django_settings
        django_comments_config = getattr(django_settings, 'DJANGO_COMMENTS', {})
        max_depth = django_comments_config.get('MAX_COMMENT_DEPTH', comments_settings.MAX_COMMENT_DEPTH)
        
        if max_depth is not None:
            parent_depth = self.parent.depth
            if parent_depth + 1 > max_depth:
                raise ValidationError({
                    'parent': _(
                        f"Maximum thread depth of {max_depth} exceeded. "
                        f"Parent is at depth {parent_depth}."
                    )
                })
    
    def save(self, *args, **kwargs):
        """
        OPTIMIZED save method that minimizes database operations.
        """
        is_new = self._state.adding
        
        # Call clean() for validation (can skip with skip_validation=True)
        if is_new and not kwargs.pop('skip_validation', False):
            self.clean()
        
        # For existing comments, just save normally
        if not is_new:
            super().save(*args, **kwargs)
            return
        
        # For new comments, handle threading setup
        with transaction.atomic():
            if self.parent:
                # === CHILD COMMENT ===
                # _validate_parent() already called in clean()
                self.thread_id = self.parent.thread_id
                self.path = 'PENDING'
                super().save(*args, **kwargs)
                final_path = f"{self.parent.path}/{self.pk}"
                type(self).objects.filter(pk=self.pk).update(path=final_path)
                self.path = final_path
                logger.debug(
                    f"Created child comment {self.pk} with path: {self.path}, "
                    f"thread_id: {self.thread_id}"
                )
            else:
                # === ROOT COMMENT ===
                self.path = 'PENDING'
                self.thread_id = 'PENDING'
                super().save(*args, **kwargs)
                final_path = str(self.pk)
                final_thread_id = str(self.pk)
                type(self).objects.filter(pk=self.pk).update(
                    path=final_path,
                    thread_id=final_thread_id
                )
                self.path = final_path
                self.thread_id = final_thread_id
                logger.debug(
                    f"Created root comment {self.pk} with path: {self.path}, "
                    f"thread_id: {self.thread_id}"
                )
    
    def delete(self, *args, **kwargs):
        """Delete related flags before deleting comment."""
        # Use the GenericRelation to delete related flags
        self.flags.all().delete()
        
        # Delete the comment
        return super().delete(*args, **kwargs)

    
    def get_user_name(self):
        """Return the user's name or 'Anonymous'."""
        if self.user:
            name = self.user.get_full_name() or self.user.get_username()
            if hasattr(self.user, 'is_staff') and self.user.is_staff:
                return f"{name} (Admin)"
            elif hasattr(self.user, 'is_superuser') and self.user.is_superuser:
                return f"{name} (Super Admin)"
            return name
        return self.user_name or _('Anonymous')
    
    def get_descendants(self):
        """Get all descendants of this comment."""
        return type(self).objects.filter(
            path__startswith=f"{self.path}/"
        ).select_related('user', 'content_type')

    def get_ancestors(self):
        """Get all ancestors of this comment."""
        if not self.parent:
            return type(self).objects.none()
        
        ancestor_ids = self.path.split('/')[:-1]
        return type(self).objects.filter(
            pk__in=ancestor_ids
        ).select_related('user', 'content_type').order_by('path')
    
    @property
    def depth(self):
        """Return the depth of this comment in the tree (0 for root)."""
        if not self.path:
            return 0
        return self.path.count('/')
    
    @property
    def is_edited(self):
        """Return True if the comment has been edited (30s grace period)."""
        if not self.created_at or not self.updated_at:
            return False
        return self.updated_at - self.created_at > timezone.timedelta(seconds=30)


class Comment(AbstractCommentBase, BaseCommentMixin):
    """
    Comment model with UUID primary key.
    
    Works with ANY model that has ANY primary key type (int, UUID, custom).
    The object_id CharField handles all PK types by storing them as strings.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID")
    )
    
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        verbose_name=_('Parent comment'),
        blank=True,
        null=True,
        related_name='children'
    )
    
    flags = GenericRelation(
        'CommentFlag',
        content_type_field='comment_type',
        object_id_field='comment_id',
        related_query_name='comment'
    )

    objects = CommentManager.from_queryset(CommentQuerySet)()
    
    class Meta:
        verbose_name = _('Comment')
        verbose_name_plural = _('Comments')
        ordering = ('-created_at',)
        permissions = [('can_moderate_comments', _('Can moderate comments'))]
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_public', 'is_removed']),
            models.Index(fields=['parent']),
            models.Index(fields=['user']),
            models.Index(fields=['thread_id']),
            models.Index(fields=['path']),
        ]


class CommentFlag(models.Model):
    """
    Records user flags for comments that may be inappropriate.
    """
    
    FLAG_CHOICES = (
        ('spam', _('Spam')),
        ('harassment', _('Harassment')),
        ('hate_speech', _('Hate Speech')),
        ('violence', _('Violence/Threats')),
        ('sexual', _('Sexual Content')),
        ('misinformation', _('Misinformation')),
        ('off_topic', _('Off Topic')),
        ('offensive', _('Offensive')),
        ('inappropriate', _('Inappropriate')),
        ('other', _('Other')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID")
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('Created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated at'), auto_now=True)
    
    # GenericForeignKey to comment
    comment_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name=_('Comment Type'),
        help_text=_('The type of comment being flagged')
    )
    comment_id = models.CharField(
        _('Comment ID'),
        max_length=255,
        help_text=_('The ID of the comment (supports both integer and UUID)')
    )
    comment = GenericForeignKey('comment_type', 'comment_id')
    
    # User who flagged
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,  
        null=True,  
        verbose_name=_('User'),
        related_name='comment_flags',
        help_text=_('The user who flagged this comment')
    )
    
    # Flag details
    flag = models.CharField(
        _('Flag'),
        max_length=30,
        choices=FLAG_CHOICES,
        default='other',
        db_index=True
    )
    
    reason = models.TextField(
        _('Reason'),
        blank=True,
        help_text=_('Optional reason for flagging')
    )
    
    # Review status
    reviewed = models.BooleanField(
        _('Reviewed'),
        default=False,
        help_text=_('Whether this flag has been reviewed by a moderator')
    )
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Reviewed By'),
        related_name='flags_reviewed'
    )
    
    reviewed_at = models.DateTimeField(
        _('Reviewed At'),
        null=True,
        blank=True
    )
    
    REVIEW_ACTION_CHOICES = (
        ('dismissed', _('Dismissed')),
        ('actioned', _('Actioned')),
    )
    
    review_action = models.CharField(
        _('Review Action'),
        max_length=20,
        choices=REVIEW_ACTION_CHOICES,
        blank=True
    )
    
    review_notes = models.TextField(
        _('Review Notes'),
        blank=True
    )
    
    # Manager
    objects = CommentFlagManager()
    
    class Meta:
        verbose_name = _('Comment flag')
        verbose_name_plural = _('Comment flags')
        
        constraints = [
            models.UniqueConstraint(
                fields=['comment_type', 'comment_id', 'user', 'flag'],
                name='unique_comment_user_flag',
                violation_error_message=_(
                    'You have already flagged this comment with this flag type.'
                )
            )
        ]
                
        indexes = [
            models.Index(
                fields=['comment_type', 'comment_id'],
                name='commentflag_comment_idx'
            ),
            models.Index(
                fields=['user', 'flag'],
                name='commentflag_user_flag_idx'
            ),
            models.Index(
                fields=['flag', 'created_at'],
                name='commentflag_flag_date_idx'
            ),
            models.Index(
                fields=['reviewed', 'created_at'],
                name='commentflag_review_idx'
            ),
        ]
        
        ordering = ['-created_at']
    
    def __str__(self):
        """String representation."""
        try:
            comment_pk = self.comment_id
            if self.user:
                user_name = self.user.get_username()
            else:
                user_name = 'Deleted User'
            return _('{user} flagged comment {comment} as {flag}').format(
                user=user_name,
                comment=comment_pk,
                flag=self.get_flag_display()
            )
        except Exception:
            return f'CommentFlag {self.pk}'
    
    def clean(self):
        """
        Validate the flag before saving.
        
        OPTIMIZED & SECURED:
        - Skips validation if explicitly disabled via __skip_clean_validation
        - Double underscore makes it harder to accidentally misuse
        - Caches validation results per instance
        - Minimal database queries
        
        Security Note:
            The __skip_clean_validation flag should ONLY be used in controlled
            bulk operations where data has already been validated. This is now
            harder to misuse due to name mangling.
        """
        super(CommentFlag, self).clean()
        
        # This makes the flag harder to access accidentally
        if getattr(self, '_CommentFlag__skip_clean_validation', False):
            return
        
        # Skip if comment object is already loaded via GenericForeignKey
        if hasattr(self, '_comment_cache') and self._comment_cache is not None:
            return
        
        # Skip validation if required fields aren't set yet
        if not self.comment_type or not self.comment_id:
            return
        
        cache_key = f'_validated_{self.comment_type.pk}_{self.comment_id}'
        if getattr(self, cache_key, False):
            return
        
        try:
            model_class = self.comment_type.model_class()
            if model_class:
                exists = model_class.objects.filter(
                    pk=self.comment_id
                ).only('pk').exists()
                
                if not exists:
                    raise ValidationError({
                        'comment_id': _(
                            f'Comment with ID {self.comment_id} does not exist.'
                        )
                    })
                setattr(self, cache_key, True)
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating comment reference: {e}")
            raise ValidationError({
                'comment': _('Invalid comment reference: {error}').format(error=str(e))
            })

    def mark_reviewed(self, moderator, action, notes=''):
        """Mark this flag as reviewed."""
        valid_actions = [choice[0] for choice in self.REVIEW_ACTION_CHOICES]
        if action and action not in valid_actions:
            raise ValueError(
                f"Invalid review action '{action}'. "
                f"Must be one of: {', '.join(valid_actions)}"
            )
        
        self.reviewed = True
        self.reviewed_by = moderator
        self.reviewed_at = timezone.now()
        self.review_action = action
        self.review_notes = notes
        self.save(update_fields=['reviewed', 'reviewed_by', 'reviewed_at', 'review_action', 'review_notes'])


class BannedUser(models.Model):
    """
    Track users who are banned from commenting.
    Supports both permanent and temporary bans.

    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID")
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_('User'),
        related_name='comment_bans'
    )
    
    banned_until = models.DateTimeField(
        _('Banned Until'),
        null=True,
        blank=True,
        help_text=_('Leave empty for permanent ban')
    )
    
    reason = models.TextField(
        _('Reason'),
        help_text=_('Reason for banning this user')
    )
    
    banned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('Banned By'),
        related_name='users_banned'
    )
    
    created_at = models.DateTimeField(_('Created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('Banned User')
        verbose_name_plural = _('Banned Users')
        ordering = ['-created_at']
        
        
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                name='unique_banned_user',
                violation_error_message=_('This user is already banned.')
            )
        ]
        
        indexes = [
            models.Index(fields=['user', 'banned_until'], name='django_comm_user_id_ban_idx'),
        ]
    
    def __str__(self):
        if self.banned_until:
            return _("{user} banned until {date}").format(
                user=self.user.get_username(),
                date=self.banned_until.strftime('%Y-%m-%d')
            )
        return _("{user} permanently banned").format(user=self.user.get_username())
    
    def clean(self):
        """Validate ban before saving."""
        super().clean()
        
        # Validate reason is not empty
        if not self.reason or not self.reason.strip():
            raise ValidationError({
                'reason': _('Ban reason cannot be empty.')
            })
        
        # Validate banned_until is not in the past
        if self.banned_until is not None:
            if self.banned_until <= timezone.now():
                raise ValidationError({
                    'banned_until': _('Ban expiration date cannot be in the past.')
                })
    
    @property
    def is_active(self):
        """Check if ban is currently active."""
        if self.banned_until is None:
            return True  # Permanent ban
        return timezone.now() < self.banned_until
    
    @classmethod
    def is_user_banned(cls, user):
        """
        Check if a user is currently banned (simple boolean check).
        
        For detailed ban info, use check_user_banned() instead.
        """
        is_banned, _ = cls.check_user_banned(user)
        return is_banned
    
    @classmethod
    def check_user_banned(cls, user):
        """
        Check if user is banned with detailed information.

        """
        if not user or not user.is_authenticated:
            return False, None
        
        # Query for active bans (permanent or temporary still active)
        active_ban = cls.objects.filter(
            user=user
        ).filter(
            models.Q(banned_until__isnull=True) |  # Permanent ban
            models.Q(banned_until__gt=timezone.now())  # Active temporary ban
        ).select_related('banned_by').first()
        
        if active_ban:
            ban_info = {
                'reason': active_ban.reason,
                'banned_until': active_ban.banned_until,
                'is_permanent': active_ban.banned_until is None,
                'banned_by': active_ban.banned_by,
                'ban_object': active_ban,
            }
            return True, ban_info
        
        return False, None


class CommentRevision(models.Model):
    """
    Track edit history of comments.
    Stores previous versions for audit trail.

    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID")
    )
    
    # GenericForeignKey to support Comment
    comment_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name=_('Comment Type')
    )
    comment_id = models.CharField(_('Comment ID'), max_length=255)
    comment = GenericForeignKey('comment_type', 'comment_id')
    
    content = models.TextField(
        _('Content'),
        help_text=_('Previous version of comment content')
    )
    
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('Edited By')
    )
    
    edited_at = models.DateTimeField(_('Edited At'), auto_now_add=True)
    
    # Snapshot of comment state at time of edit
    was_public = models.BooleanField(_('Was Public'), default=True)
    was_removed = models.BooleanField(_('Was Removed'), default=False)
    
    class Meta:
        verbose_name = _('Comment Revision')
        verbose_name_plural = _('Comment Revisions')
        ordering = ['-edited_at']
        indexes = [
            models.Index(fields=['comment_type', 'comment_id'], name='commentrev_comment_idx'),
            models.Index(fields=['edited_at'], name='commentrev_edited_idx'),
        ]
    
    def __str__(self):
        return _("Revision of comment {comment_id} at {date}").format(
            comment_id=self.comment_id,
            date=self.edited_at.strftime('%Y-%m-%d %H:%M')
        )




class ModerationAction(models.Model):
    """
    Log all moderation actions for accountability.
    Tracks who did what and when.

    """
    
    ACTION_CHOICES = (
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('deleted', _('Deleted')),
        ('edited', _('Edited')),
        ('flagged', _('Flagged')),
        ('unflagged', _('Unflagged')),
        ('banned_user', _('Banned User')),
        ('unbanned_user', _('Unbanned User')),
    )
    
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID")
    )
    
    # GenericForeignKey to support Comment
    comment_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name=_('Comment Type'),
        null=True,
        blank=True
    )
    comment_id = models.CharField(_('Comment ID'), max_length=255, blank=True)
    comment = GenericForeignKey('comment_type', 'comment_id')
    
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('Moderator'),
        related_name='moderation_actions'
    )
    
    action = models.CharField(
        _('Action'),
        max_length=20,
        choices=ACTION_CHOICES
    )
    
    reason = models.TextField(
        _('Reason'),
        blank=True,
        help_text=_('Reason for this action')
    )
    
    # For ban actions
    affected_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Affected User'),
        related_name='moderation_actions_received'
    )
    
    timestamp = models.DateTimeField(_('Timestamp'), auto_now_add=True)
    
    # Additional metadata
    ip_address = models.GenericIPAddressField(
        _('IP Address'),
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = _('Moderation Action')
        verbose_name_plural = _('Moderation Actions')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['comment_type', 'comment_id'], name='modaction_comment_idx'),
            models.Index(fields=['moderator', 'action'], name='modaction_mod_idx'),
            models.Index(fields=['timestamp'], name='modaction_time_idx'),
        ]
    
    def __str__(self):
        return _("{moderator} {action} at {time}").format(
            moderator=self.moderator.get_username() if self.moderator else 'System',
            action=self.get_action_display(),
            time=self.timestamp.strftime('%Y-%m-%d %H:%M')
        )