"""
Celery tasks for django-reusable-comments.

This module provides optional Celery task support for asynchronous email notifications.
Celery is NOT required - notifications work synchronously by default.

To enable async notifications:
1. Install celery: pip install celery
2. Configure Celery in your Django project
3. Set DJANGO_COMMENTS['USE_ASYNC_NOTIFICATIONS'] = True
4. Start Celery workers: celery -A your_project worker -l info
"""
import logging
from typing import Optional

from .conf import comments_settings
from .utils import get_comment_model

logger = logging.getLogger(comments_settings.LOGGER_NAME)

# Try to import Celery - it's optional
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    # Define a no-op decorator if Celery isn't installed
    def shared_task(*args, **kwargs):
        """Dummy decorator when Celery is not available."""
        def decorator(func):
            return func
        return decorator


# ============================================================================
# CELERY TASKS - All tasks use the same pattern:
# 1. Fetch the object from database
# 2. Call the synchronous notification function
# 3. Log any errors
# ============================================================================

@shared_task(name='django_comments.notify_new_comment', bind=True, max_retries=3)
def notify_new_comment_task(self, comment_id: str):
    """
    Async task to notify about a new comment.
    
    Args:
        comment_id: Comment primary key (UUID as string)
    """
    try:
        Comment = get_comment_model()
        comment = Comment.objects.get(pk=comment_id)
        
        # Import and call synchronous notification
        from .notifications import notification_service
        notification_service.notify_new_comment(comment)
        
        logger.info(f"[Celery] Sent new comment notification for {comment_id}")
        
    except Comment.DoesNotExist:
        logger.error(f"[Celery] Comment {comment_id} not found for notification")
    except Exception as exc:
        logger.error(f"[Celery] Failed to send new comment notification: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(name='django_comments.notify_comment_reply', bind=True, max_retries=3)
def notify_comment_reply_task(self, comment_id: str, parent_comment_id: str):
    """
    Async task to notify about a comment reply.
    
    Args:
        comment_id: Reply comment primary key (UUID as string)
        parent_comment_id: Parent comment primary key (UUID as string)
    """
    try:
        Comment = get_comment_model()
        comment = Comment.objects.get(pk=comment_id)
        parent_comment = Comment.objects.get(pk=parent_comment_id)
        
        from .notifications import notification_service
        notification_service.notify_comment_reply(comment, parent_comment)
        
        logger.info(f"[Celery] Sent reply notification for {comment_id}")
        
    except Comment.DoesNotExist as e:
        logger.error(f"[Celery] Comment not found for reply notification: {e}")
    except Exception as exc:
        logger.error(f"[Celery] Failed to send reply notification: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(name='django_comments.notify_comment_approved', bind=True, max_retries=3)
def notify_comment_approved_task(self, comment_id: str, moderator_id: Optional[int] = None):
    """
    Async task to notify that a comment was approved.
    
    Args:
        comment_id: Comment primary key (UUID as string)
        moderator_id: Moderator user ID (optional)
    """
    try:
        Comment = get_comment_model()
        comment = Comment.objects.get(pk=comment_id)
        
        moderator = None
        if moderator_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            moderator = User.objects.get(pk=moderator_id)
        
        from .notifications import notification_service
        notification_service.notify_comment_approved(comment, moderator)
        
        logger.info(f"[Celery] Sent approval notification for {comment_id}")
        
    except Exception as exc:
        logger.error(f"[Celery] Failed to send approval notification: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(name='django_comments.notify_comment_rejected', bind=True, max_retries=3)
def notify_comment_rejected_task(self, comment_id: str, moderator_id: Optional[int] = None):
    """
    Async task to notify that a comment was rejected.
    
    Args:
        comment_id: Comment primary key (UUID as string)
        moderator_id: Moderator user ID (optional)
    """
    try:
        Comment = get_comment_model()
        comment = Comment.objects.get(pk=comment_id)
        
        moderator = None
        if moderator_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            moderator = User.objects.get(pk=moderator_id)
        
        from .notifications import notification_service
        notification_service.notify_comment_rejected(comment, moderator)
        
        logger.info(f"[Celery] Sent rejection notification for {comment_id}")
        
    except Exception as exc:
        logger.error(f"[Celery] Failed to send rejection notification: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(name='django_comments.notify_moderators', bind=True, max_retries=3)
def notify_moderators_task(self, comment_id: str):
    """
    Async task to notify moderators about a comment needing approval.
    
    Args:
        comment_id: Comment primary key (UUID as string)
    """
    try:
        Comment = get_comment_model()
        comment = Comment.objects.get(pk=comment_id)
        
        from .notifications import notification_service
        notification_service.notify_moderators(comment)
        
        logger.info(f"[Celery] Sent moderator notification for {comment_id}")
        
    except Exception as exc:
        logger.error(f"[Celery] Failed to send moderator notification: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(name='django_comments.notify_moderators_of_flag', bind=True, max_retries=3)
def notify_moderators_of_flag_task(self, comment_id: str, flag_id: str, flag_count: int):
    """
    Async task to notify moderators about a flagged comment.
    
    Args:
        comment_id: Comment primary key (UUID as string)
        flag_id: CommentFlag primary key (UUID as string)
        flag_count: Total number of flags on the comment
    """
    try:
        Comment = get_comment_model()
        from .models import CommentFlag
        
        comment = Comment.objects.get(pk=comment_id)
        flag = CommentFlag.objects.get(pk=flag_id)
        
        from .notifications import notification_service
        
        recipients = notification_service._get_moderator_emails()
        if not recipients:
            logger.debug("[Celery] No moderator emails configured for flag notifications")
            return
        
        context = notification_service._get_notification_context(comment)
        context['flag'] = flag
        context['flag_count'] = flag_count
        context['flag_type'] = flag.get_flag_display()
        context['flag_reason'] = flag.reason
        context['flagger'] = flag.user
        
        from django.utils.translation import gettext_lazy as _
        subject = _("Comment flagged as {flag_type} ({count} total flags)").format(
            flag_type=flag.get_flag_display(),
            count=flag_count
        )
        
        notification_service._send_notification_email(
            recipients=recipients,
            subject=subject,
            template=comments_settings.NOTIFICATION_FLAG_TEMPLATE,
            context=context
        )
        
        logger.info(f"[Celery] Sent flag notification for {comment_id}")
        
    except Exception as exc:
        logger.error(f"[Celery] Failed to send flag notification: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(name='django_comments.notify_auto_hide', bind=True, max_retries=3)
def notify_auto_hide_task(self, comment_id: str, flag_count: int):
    """
    Async task to notify moderators that a comment was auto-hidden.
    
    Args:
        comment_id: Comment primary key (UUID as string)
        flag_count: Number of flags that triggered auto-hide
    """
    try:
        Comment = get_comment_model()
        comment = Comment.objects.get(pk=comment_id)
        
        from .notifications import notification_service
        
        recipients = notification_service._get_moderator_emails()
        if not recipients:
            return
        
        context = notification_service._get_notification_context(comment)
        context['flag_count'] = flag_count
        context['threshold'] = comments_settings.AUTO_HIDE_THRESHOLD
        context['auto_action'] = 'hidden'
        
        from django.utils.translation import gettext_lazy as _
        subject = _("Comment auto-hidden after {count} flags").format(count=flag_count)
        
        notification_service._send_notification_email(
            recipients=recipients,
            subject=subject,
            template=comments_settings.NOTIFICATION_MODERATOR_TEMPLATE,
            context=context
        )
        
        logger.info(f"[Celery] Sent auto-hide notification for {comment_id}")
        
    except Exception as exc:
        logger.error(f"[Celery] Failed to send auto-hide notification: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(name='django_comments.notify_user_banned', bind=True, max_retries=3)
def notify_user_banned_task(self, ban_id: str):
    """
    Async task to notify a user they've been banned.
    
    Args:
        ban_id: BannedUser primary key (UUID as string)
    """
    try:
        from .models import BannedUser
        ban = BannedUser.objects.get(pk=ban_id)
        
        if not ban.user.email:
            logger.debug(f"[Celery] User {ban.user.pk} has no email, skipping ban notification")
            return
        
        from .notifications import notification_service
        from django.utils.translation import gettext_lazy as _
        from django.utils import timezone
        
        recipients = [ban.user.email]
        context = notification_service._get_notification_context(None)
        context['ban'] = ban
        context['user'] = ban.user
        
        if ban.banned_until:
            subject = _("Your commenting privileges have been suspended until {date}").format(
                date=ban.banned_until.strftime('%Y-%m-%d')
            )
        else:
            subject = _("Your commenting privileges have been permanently suspended")
        
        notification_service._send_notification_email(
            recipients=recipients,
            subject=subject,
            template=comments_settings.NOTIFICATION_USER_BAN_TEMPLATE,
            context=context
        )
        
        logger.info(f"[Celery] Sent ban notification to user {ban.user.pk}")
        
    except Exception as exc:
        logger.error(f"[Celery] Failed to send ban notification: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(name='django_comments.notify_user_unbanned', bind=True, max_retries=3)
def notify_user_unbanned_task(self, user_id: int, unbanned_by_id: Optional[int] = None, 
                               original_ban_reason: str = ''):
    """
    Async task to notify a user they've been unbanned.
    
    Args:
        user_id: User primary key
        unbanned_by_id: User who lifted the ban (optional)
        original_ban_reason: The reason for the original ban
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = User.objects.get(pk=user_id)
        
        if not user.email:
            logger.debug(f"[Celery] User {user_id} has no email, skipping unban notification")
            return
        
        unbanned_by = None
        if unbanned_by_id:
            unbanned_by = User.objects.get(pk=unbanned_by_id)
        
        from .notifications import notification_service
        from django.utils.translation import gettext_lazy as _
        from django.utils import timezone
        
        recipients = [user.email]
        context = notification_service._get_notification_context(None)
        context['user'] = user
        context['unbanned_by'] = unbanned_by
        context['original_ban_reason'] = original_ban_reason
        context['unban_date'] = timezone.now()
        
        subject = _("Your commenting privileges have been restored on {site_name}").format(
            site_name=context['site_name']
        )
        
        notification_service._send_notification_email(
            recipients=recipients,
            subject=subject,
            template=comments_settings.NOTIFICATION_USER_UNBAN_TEMPLATE,
            context=context
        )
        
        logger.info(f"[Celery] Sent unban notification to user {user_id}")
        
    except Exception as exc:
        logger.error(f"[Celery] Failed to send unban notification: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))