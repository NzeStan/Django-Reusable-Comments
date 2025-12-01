from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .conf import comments_settings
from .managers import CommentManager, CommentQuerySet
from .utils import get_comment_model_path

import uuid
import logging

logger = logging.getLogger('django_comments')


class AbstractCommentBase(models.Model):
    """
    Abstract base class for all comment models.
    """
    # If True, use UUIDs for primary keys, otherwise use integers
    if comments_settings.USE_UUIDS:
        id = models.UUIDField(
            primary_key=True,
            default=uuid.uuid4,
            editable=False,
            verbose_name=_("ID")
        )
    
    created_at = models.DateTimeField(
        _('Created at'),
        default=timezone.now
    )
    updated_at = models.DateTimeField(
        _('Updated at'),
        auto_now=True
    )
    
    class Meta:
        abstract = True


class Comment(AbstractCommentBase):
    """
    A comment that can be attached to any model instance.
    """
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name=_('Content type'),
        related_name='comments'
    )
    
    # Always use TextField for object_id - it can handle both UUIDs and integers
    object_id = models.TextField(_('Object ID'))
    
    # The GenericForeignKey to the related object
    content_object = GenericForeignKey('content_type', 'object_id')
    # User information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='comments'
    )
    user_name = models.CharField(
        _('User name'),
        max_length=100,
        blank=True
    )
    user_email = models.EmailField(
        _('User email'),
        blank=True
    )
    user_url = models.URLField(
        _('User URL'),
        blank=True,
    )
    
    # IP and User Agent
    ip_address = models.GenericIPAddressField(
        _('IP address'),
        blank=True,
        null=True
    )
    user_agent = models.TextField(
        _('User agent'),
        blank=True
    )
    
    # Comment content
    content = models.TextField(
        _('Content')
    )
    
    # Moderation fields
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
    
    # Threading support
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        verbose_name=_('Parent comment'),
        blank=True,
        null=True,
        related_name='children'
    )
    
    # For efficient comment tree display
    path = models.CharField(
        _('Materialized path'),
        max_length=255,
        blank=True,
        db_index=True,
        help_text=_('Used for storing hierarchical comment structure')
    )
    
    # For efficient ordering
    thread_id = models.CharField(
        _('Thread ID'),
        max_length=255,
        blank=True,
        db_index=True
    )
    
    # Manager
    objects = CommentManager.from_queryset(CommentQuerySet)()
    
    class Meta:
        verbose_name = _('Comment')
        verbose_name_plural = _('Comments')
        ordering = ('-created_at',)
        permissions = [
            ('can_moderate_comments', _('Can moderate comments')),
        ]
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_public', 'is_removed']),
            models.Index(fields=['parent']),
            models.Index(fields=['user']),
            models.Index(fields=['thread_id']),
            models.Index(fields=['is_public', 'is_removed', 'created_at']),  # Common filter combo
            models.Index(fields=['content_type', 'object_id', 'is_public']),  # For public comments query
            models.Index(fields=['user', 'created_at']),  # For user's comments
        ]
        
    def __str__(self):
        return _("Comment by {user} on {object}").format(
            user=self.get_user_name(),
            object=str(self.content_object)
        )
    
    def save(self, *args, **kwargs):
        
        is_new = self._state.adding

        # First save (to get a primary key)
        super().save(*args, **kwargs)

        if is_new:
            if self.parent:
                self.path = f"{self.parent.path}/{self.pk}"
                self.thread_id = self.parent.thread_id
            else:
                self.path = str(self.pk)
                self.thread_id = str(self.pk)

            # Avoid recursion
            type(self).objects.filter(pk=self.pk).update(
                path=self.path,
                thread_id=self.thread_id
            )
            print(f"[DEBUG] Comment.save() called — pk={self.pk}, parent={self.parent}")
            print(f"[DEBUG] Created comment: path={self.path}, thread_id={self.thread_id}")
    
    def get_absolute_url(self):
        """Get URL for viewing the comment."""
        return reverse('django_comments:comment_detail', args=[self.pk])
    
    def get_user_name(self):
        """Return the user's name or 'Anonymous', with admin indicator if applicable."""
        if self.user:
            name = self.user.get_full_name() or self.user.get_username()
            # Add admin indicator if user is admin
            if hasattr(self.user, 'is_staff') and self.user.is_staff:
                return f"{name} (Admin)"
            elif hasattr(self.user, 'is_superuser') and self.user.is_superuser:
                return f"{name} (Super Admin)"
            return name
        return self.user_name or _('Anonymous')
    
    def get_descendants(self):
        """Get all descendants of this comment."""
        return type(self).objects.filter(path__startswith=f"{self.path}/")
    
    def get_ancestors(self):
        """Get all ancestors of this comment."""
        if not self.parent:
            return type(self).objects.none()
        
        # Split the path by '/' and get all parent IDs
        ancestor_ids = self.path.split('/')[:-1]
        return type(self).objects.filter(pk__in=ancestor_ids)
    
    @property
    def depth(self):
        """Return the depth of this comment in the tree."""
        if not self.path:
            return 0
        return self.path.count('/')
    
    @property
    def is_edited(self):
        """Return True if the comment has been edited."""
        if not self.created_at or not self.updated_at:
            return False
        return self.updated_at - self.created_at > timezone.timedelta(seconds=30)


class CommentFlag(AbstractCommentBase):
    """
    Records user flags for comments that may be inappropriate.
    """
    FLAG_CHOICES = (
        ('spam', _('Spam')),
        ('offensive', _('Offensive')),
        ('inappropriate', _('Inappropriate')),
        ('other', _('Other')),
    )
    
    comment = models.ForeignKey(
        get_comment_model_path(),
        on_delete=models.CASCADE,
        verbose_name=_('Comment'),
        related_name='flags'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_('User'),
        related_name='comment_flags'
    )
    flag = models.CharField(
        _('Flag'),
        max_length=30,
        choices=FLAG_CHOICES,
        default='other'
    )
    reason = models.TextField(
        _('Reason'),
        blank=True
    )
    
    class Meta:
        verbose_name = _('Comment flag')
        verbose_name_plural = _('Comment flags')
        unique_together = ('comment', 'user', 'flag')
        
    def __str__(self):
        return _("{user} flagged comment {comment} as {flag}").format(
            user=self.user.get_username(),
            comment=self.comment_id,
            flag=self.get_flag_display()
        )
    