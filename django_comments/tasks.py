"""
Background task support for django-reusable-comments.

This module provides optional async notification support via Python's built-in
threading module. No external task queue or broker is required.

To enable async (background-thread) notifications:
1. Set DJANGO_COMMENTS['USE_ASYNC_NOTIFICATIONS'] = True

When USE_ASYNC_NOTIFICATIONS is True, each notification runs inside a daemon
Thread so it does not block the HTTP request/response cycle.

Note: Thread-based tasks are fire-and-forget. They will not be retried on
failure and will not survive a process restart. For guaranteed delivery in
production, consider wrapping calls in a persistent task queue of your
choice. Failures are always logged so you can monitor and replay them.
"""
import logging
from threading import Thread
from typing import Optional

from .conf import comments_settings
from .utils import get_comment_model

logger = logging.getLogger(comments_settings.LOGGER_NAME)


def _run_in_thread(func, *args, **kwargs):
    """Run *func* in a daemon background thread and return the thread object."""
    thread = Thread(target=func, args=args, kwargs=kwargs, daemon=True)
    thread.start()
    return thread


# ============================================================================
# BACKGROUND TASKS
# Each function fetches the required objects from the database, delegates to
# the synchronous notification service, and logs the outcome.
# ============================================================================

def notify_new_comment_task(comment_id: str):
    """
    Background task: notify about a new comment.

    Args:
        comment_id: Comment primary key (UUID as string)
    """
    Comment = get_comment_model()
    try:
        comment = Comment.objects.get(pk=comment_id)

        from .notifications import notification_service
        notification_service.notify_new_comment(comment)

        logger.info(f"Sent new comment notification for {comment_id}")

    except Comment.DoesNotExist:
        logger.error(f"Comment {comment_id} not found for notification")
    except Exception as exc:
        logger.error(f"Failed to send new comment notification: {exc}")


def notify_comment_reply_task(comment_id: str, parent_comment_id: str):
    """
    Background task: notify about a comment reply.

    Args:
        comment_id: Reply comment primary key (UUID as string)
        parent_comment_id: Parent comment primary key (UUID as string)
    """
    Comment = get_comment_model()
    try:
        comment = Comment.objects.get(pk=comment_id)
        parent_comment = Comment.objects.get(pk=parent_comment_id)

        from .notifications import notification_service
        notification_service.notify_comment_reply(comment, parent_comment)

        logger.info(f"Sent reply notification for {comment_id}")

    except Comment.DoesNotExist as exc:
        logger.error(f"Comment not found for reply notification: {exc}")
    except Exception as exc:
        logger.error(f"Failed to send reply notification: {exc}")


def notify_comment_approved_task(comment_id: str, moderator_id: Optional[int] = None):
    """
    Background task: notify that a comment was approved.

    Args:
        comment_id: Comment primary key (UUID as string)
        moderator_id: Moderator user ID (optional)
    """
    Comment = get_comment_model()
    try:
        comment = Comment.objects.get(pk=comment_id)

        moderator = None
        if moderator_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            moderator = User.objects.get(pk=moderator_id)

        from .notifications import notification_service
        notification_service.notify_comment_approved(comment, moderator)

        logger.info(f"Sent approval notification for {comment_id}")

    except Exception as exc:
        logger.error(f"Failed to send approval notification: {exc}")


def notify_comment_rejected_task(comment_id: str, moderator_id: Optional[int] = None):
    """
    Background task: notify that a comment was rejected.

    Args:
        comment_id: Comment primary key (UUID as string)
        moderator_id: Moderator user ID (optional)
    """
    Comment = get_comment_model()
    try:
        comment = Comment.objects.get(pk=comment_id)

        moderator = None
        if moderator_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            moderator = User.objects.get(pk=moderator_id)

        from .notifications import notification_service
        notification_service.notify_comment_rejected(comment, moderator)

        logger.info(f"Sent rejection notification for {comment_id}")

    except Exception as exc:
        logger.error(f"Failed to send rejection notification: {exc}")


def notify_moderators_task(comment_id: str):
    """
    Background task: notify moderators about a comment needing approval.

    Args:
        comment_id: Comment primary key (UUID as string)
    """
    Comment = get_comment_model()
    try:
        comment = Comment.objects.get(pk=comment_id)

        from .notifications import notification_service
        notification_service.notify_moderators(comment)

        logger.info(f"Sent moderator notification for {comment_id}")

    except Exception as exc:
        logger.error(f"Failed to send moderator notification: {exc}")


def notify_moderators_of_flag_task(comment_id: str, flag_id: str, flag_count: int):
    """
    Background task: notify moderators about a flagged comment.

    Args:
        comment_id: Comment primary key (UUID as string)
        flag_id: CommentFlag primary key (UUID as string)
        flag_count: Total number of flags on the comment
    """
    Comment = get_comment_model()
    try:
        from .models import CommentFlag

        comment = Comment.objects.get(pk=comment_id)
        flag = CommentFlag.objects.get(pk=flag_id)

        from .notifications import notification_service

        recipients = notification_service._get_moderator_emails()
        if not recipients:
            logger.debug("No moderator emails configured for flag notifications")
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

        logger.info(f"Sent flag notification for {comment_id}")

    except Exception as exc:
        logger.error(f"Failed to send flag notification: {exc}")


def notify_auto_hide_task(comment_id: str, flag_count: int):
    """
    Background task: notify moderators that a comment was auto-hidden.

    Args:
        comment_id: Comment primary key (UUID as string)
        flag_count: Number of flags that triggered auto-hide
    """
    Comment = get_comment_model()
    try:
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

        logger.info(f"Sent auto-hide notification for {comment_id}")

    except Exception as exc:
        logger.error(f"Failed to send auto-hide notification: {exc}")


def notify_user_banned_task(ban_id: str):
    """
    Background task: notify a user they've been banned.

    Args:
        ban_id: BannedUser primary key (UUID as string)
    """
    try:
        from .models import BannedUser
        ban = BannedUser.objects.get(pk=ban_id)

        if not ban.user.email:
            logger.debug(f"User {ban.user.pk} has no email, skipping ban notification")
            return

        from .notifications import notification_service
        from django.utils.translation import gettext_lazy as _

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

        logger.info(f"Sent ban notification to user {ban.user.pk}")

    except Exception as exc:
        logger.error(f"Failed to send ban notification: {exc}")


def notify_user_unbanned_task(user_id: int, unbanned_by_id: Optional[int] = None,
                               original_ban_reason: str = ''):
    """
    Background task: notify a user they've been unbanned.

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
            logger.debug(f"User {user_id} has no email, skipping unban notification")
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

        logger.info(f"Sent unban notification to user {user_id}")

    except Exception as exc:
        logger.error(f"Failed to send unban notification: {exc}")
