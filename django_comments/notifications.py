"""
Email notification system for django-reusable-comments.

Supports both synchronous (default) and asynchronous (background thread) email
sending. No external message broker is required.

To enable async notifications:
1. Set DJANGO_COMMENTS['USE_ASYNC_NOTIFICATIONS'] = True

When async mode is active each outbound notification is dispatched to a daemon
Thread so the HTTP request returns immediately. Failures are logged but not
automatically retried.
"""
import logging
from threading import Thread
from typing import List, Optional
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.sites.models import Site
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .conf import comments_settings

logger = logging.getLogger(comments_settings.LOGGER_NAME)


class CommentNotificationService:
    """Service for sending comment notifications (sync or async via threads)."""

    def __init__(self):
        self.enabled = comments_settings.SEND_NOTIFICATIONS
        self.from_email = comments_settings.DEFAULT_FROM_EMAIL
        self.use_async = comments_settings.USE_ASYNC_NOTIFICATIONS

    def _dispatch_async(self, task_name: str, *args, **kwargs):
        """
        Dispatch a task to run in a background thread when async is enabled.

        Args:
            task_name: Name of the function in the tasks module to call
            *args, **kwargs: Arguments to pass to the task

        Returns:
            True if dispatched asynchronously, False if sync should be used.
        """
        if not self.use_async:
            return False

        try:
            from . import tasks
            task_func = getattr(tasks, task_name, None)
            if task_func and callable(task_func):
                thread = Thread(target=task_func, args=args, kwargs=kwargs, daemon=True)
                thread.start()
                logger.debug(f"Dispatched async task in background thread: {task_name}")
                return True
        except Exception as exc:
            logger.error(
                f"Failed to dispatch async task {task_name}: {exc}. Falling back to sync."
            )

        return False

    def notify_new_comment(self, comment):
        """
        Notify about a new comment.

        Args:
            comment: Comment instance
        """
        if not self.enabled:
            return

        if self._dispatch_async('notify_new_comment_task', str(comment.pk)):
            return

        try:
            recipients = self._get_comment_recipients(comment)

            if not recipients:
                logger.debug(f"No recipients for comment {comment.pk}")
                return

            context = self._get_notification_context(comment)

            subject = comments_settings.NOTIFICATION_SUBJECT.format(
                object=str(comment.content_object)
            )

            self._send_notification_email(
                recipients=recipients,
                subject=subject,
                template=comments_settings.NOTIFICATION_EMAIL_TEMPLATE,
                context=context
            )

            logger.info(
                f"Sent new comment notification for comment {comment.pk} "
                f"to {len(recipients)} recipients"
            )

        except Exception as exc:
            logger.error(f"Failed to send notification for comment {comment.pk}: {exc}")

    def notify_comment_reply(self, comment, parent_comment):
        """
        Notify about a reply to a comment.

        Args:
            comment: The reply comment
            parent_comment: The parent comment being replied to
        """
        if not self.enabled:
            return

        if self._dispatch_async(
            'notify_comment_reply_task', str(comment.pk), str(parent_comment.pk)
        ):
            return

        try:
            if parent_comment.user and parent_comment.user.email:
                recipients = [parent_comment.user.email]
            elif parent_comment.user_email:
                recipients = [parent_comment.user_email]
            else:
                return

            if comment.user and parent_comment.user and comment.user == parent_comment.user:
                return

            context = self._get_notification_context(comment)
            context['parent_comment'] = parent_comment

            subject = _("Reply to your comment on {object}").format(
                object=str(comment.content_object)
            )

            self._send_notification_email(
                recipients=recipients,
                subject=subject,
                template=comments_settings.NOTIFICATION_REPLY_TEMPLATE,
                context=context
            )

            logger.info(f"Sent reply notification for comment {comment.pk}")

        except Exception as exc:
            logger.error(f"Failed to send reply notification: {exc}")

    def notify_comment_approved(self, comment, moderator=None):
        """
        Notify comment author that their comment was approved.

        Args:
            comment: Comment instance
            moderator: User who approved the comment
        """
        if not self.enabled:
            return

        moderator_id = moderator.pk if moderator else None
        if self._dispatch_async('notify_comment_approved_task', str(comment.pk), moderator_id):
            return

        try:
            if comment.user and comment.user.email:
                recipients = [comment.user.email]
            elif comment.user_email:
                recipients = [comment.user_email]
            else:
                return

            context = self._get_notification_context(comment)
            context['moderator'] = moderator

            subject = _("Your comment on {object} was approved").format(
                object=str(comment.content_object)
            )

            self._send_notification_email(
                recipients=recipients,
                subject=subject,
                template=comments_settings.NOTIFICATION_APPROVED_TEMPLATE,
                context=context
            )

            logger.info(f"Sent approval notification for comment {comment.pk}")

        except Exception as exc:
            logger.error(f"Failed to send approval notification: {exc}")

    def notify_comment_rejected(self, comment, moderator=None):
        """
        Notify comment author that their comment was rejected.

        Args:
            comment: Comment instance
            moderator: User who rejected the comment
        """
        if not self.enabled:
            return

        moderator_id = moderator.pk if moderator else None
        if self._dispatch_async('notify_comment_rejected_task', str(comment.pk), moderator_id):
            return

        try:
            if comment.user and comment.user.email:
                recipients = [comment.user.email]
            elif comment.user_email:
                recipients = [comment.user_email]
            else:
                return

            context = self._get_notification_context(comment)
            context['moderator'] = moderator

            subject = _("Your comment on {object} requires changes").format(
                object=str(comment.content_object)
            )

            self._send_notification_email(
                recipients=recipients,
                subject=subject,
                template=comments_settings.NOTIFICATION_REJECTED_TEMPLATE,
                context=context
            )

            logger.info(f"Sent rejection notification for comment {comment.pk}")

        except Exception as exc:
            logger.error(f"Failed to send rejection notification: {exc}")

    def notify_moderators(self, comment):
        """
        Notify moderators about a new comment that needs approval.

        Args:
            comment: Comment instance
        """
        if not self.enabled:
            return

        if self._dispatch_async('notify_moderators_task', str(comment.pk)):
            return

        try:
            recipients = self._get_moderator_emails()

            if not recipients:
                logger.debug("No moderator emails configured")
                return

            context = self._get_notification_context(comment)

            subject = _("New comment awaiting moderation on {object}").format(
                object=str(comment.content_object)
            )

            self._send_notification_email(
                recipients=recipients,
                subject=subject,
                template=comments_settings.NOTIFICATION_MODERATOR_TEMPLATE,
                context=context
            )

            logger.info(f"Sent moderation notification for comment {comment.pk}")

        except Exception as exc:
            logger.error(f"Failed to send moderator notification: {exc}")

    def _get_comment_recipients(self, comment) -> List[str]:
        """
        Get list of email addresses to notify about a comment.
        Override this method to customize recipient logic.
        """
        recipients = []

        if hasattr(comment.content_object, 'author'):
            author = comment.content_object.author
            if hasattr(author, 'email') and author.email:
                recipients.append(author.email)
        elif hasattr(comment.content_object, 'user'):
            user = comment.content_object.user
            if hasattr(user, 'email') and user.email:
                recipients.append(user.email)

        notification_emails = comments_settings.COMMENT_NOTIFICATION_EMAILS
        recipients.extend(notification_emails)

        recipients = list(set(recipients))
        if comment.user and comment.user.email:
            recipients = [r for r in recipients if r != comment.user.email]
        elif comment.user_email:
            recipients = [r for r in recipients if r != comment.user_email]

        return recipients

    def _get_moderator_emails(self) -> List[str]:
        """Get list of moderator email addresses."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        moderators = User.objects.filter(
            groups__permissions__codename='can_moderate_comments'
        ).distinct()

        emails = [u.email for u in moderators if u.email]

        staff = User.objects.filter(is_staff=True).distinct()
        emails.extend([u.email for u in staff if u.email and u.email not in emails])

        return emails

    def _get_notification_context(self, comment) -> dict:
        """
        Build context dictionary for email templates.

        Args:
            comment: Comment instance or None (for ban notifications)

        Returns:
            dict: Context for email template
        """
        try:
            site = Site.objects.get_current()
            domain = site.domain
            site_name = site.name
        except Exception:
            domain = comments_settings.SITE_DOMAIN or 'example.com'
            site_name = comments_settings.SITE_NAME or 'Our Site'

        protocol = 'https' if comments_settings.USE_HTTPS else 'http'

        context = {
            'site_name': site_name,
            'domain': domain,
            'protocol': protocol,
        }

        if comment is not None:
            context['comment'] = comment
            context['content_object'] = comment.content_object

        return context

    def _send_notification_email(
        self,
        recipients: List[str],
        subject: str,
        template: str,
        context: dict
    ):
        """
        Send notification email.

        Args:
            recipients: List of email addresses
            subject: Email subject
            template: Template path
            context: Template context
        """
        try:
            html_body = render_to_string(template, context)

            text_template = template.replace('.html', '.txt')
            try:
                text_body = render_to_string(text_template, context)
            except Exception:
                import re
                text_body = re.sub('<[^<]+?>', '', html_body)

            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=self.from_email,
                to=recipients
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=False)

        except Exception as exc:
            logger.error(f"Failed to send email: {exc}")
            raise


# Global notification service instance
notification_service = CommentNotificationService()


# ============================================================================
# CONVENIENCE FUNCTIONS
# These are the public API for sending notifications
# ============================================================================

def notify_new_comment(comment):
    """Notify about a new comment."""
    notification_service.notify_new_comment(comment)


def notify_comment_reply(comment, parent_comment):
    """Notify about a reply to a comment."""
    notification_service.notify_comment_reply(comment, parent_comment)


def notify_comment_approved(comment, moderator=None):
    """Notify that a comment was approved."""
    notification_service.notify_comment_approved(comment, moderator)


def notify_comment_rejected(comment, moderator=None):
    """Notify that a comment was rejected."""
    notification_service.notify_comment_rejected(comment, moderator)


def notify_moderators(comment):
    """Notify moderators about a comment needing approval."""
    notification_service.notify_moderators(comment)


def notify_moderators_of_flag(comment, flag, flag_count):
    """
    Notify moderators that a comment has been flagged.

    Args:
        comment: Comment instance
        flag: CommentFlag instance
        flag_count: Total number of flags on this comment
    """
    if not comments_settings.SEND_NOTIFICATIONS or not comments_settings.NOTIFY_ON_FLAG:
        return

    if notification_service.use_async:
        if notification_service._dispatch_async(
            'notify_moderators_of_flag_task',
            str(comment.pk),
            str(flag.pk),
            flag_count
        ):
            return

    try:
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

        logger.info(f"Sent flag notification for comment {comment.pk}")

    except Exception as exc:
        logger.error(f"Failed to send flag notification: {exc}")


def notify_auto_hide(comment, flag_count):
    """
    Notify moderators that a comment was auto-hidden.

    Args:
        comment: Comment instance
        flag_count: Number of flags that triggered auto-hide
    """
    if not comments_settings.SEND_NOTIFICATIONS or not comments_settings.NOTIFY_ON_AUTO_HIDE:
        return

    if notification_service.use_async:
        if notification_service._dispatch_async(
            'notify_auto_hide_task', str(comment.pk), flag_count
        ):
            return

    try:
        recipients = notification_service._get_moderator_emails()

        if not recipients:
            return

        context = notification_service._get_notification_context(comment)
        context['flag_count'] = flag_count
        context['threshold'] = comments_settings.AUTO_HIDE_THRESHOLD
        context['auto_action'] = 'hidden'

        subject = _("Comment auto-hidden after {count} flags").format(count=flag_count)

        notification_service._send_notification_email(
            recipients=recipients,
            subject=subject,
            template=comments_settings.NOTIFICATION_MODERATOR_TEMPLATE,
            context=context
        )

        logger.info(f"Sent auto-hide notification for comment {comment.pk}")

    except Exception as exc:
        logger.error(f"Failed to send auto-hide notification: {exc}")


def notify_user_banned(ban):
    """
    Notify user that they have been banned.

    Args:
        ban: BannedUser instance
    """
    if not comments_settings.SEND_NOTIFICATIONS:
        return

    if notification_service.use_async:
        if notification_service._dispatch_async('notify_user_banned_task', str(ban.pk)):
            return

    try:
        if not ban.user.email:
            logger.debug(f"User {ban.user.pk} has no email, skipping ban notification")
            return

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
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


def notify_user_unbanned(user, unbanned_by=None, original_ban_reason=''):
    """
    Notify user that they have been unbanned.

    Args:
        user: User instance
        unbanned_by: User who lifted the ban (optional)
        original_ban_reason: The reason for the original ban
    """
    if not comments_settings.SEND_NOTIFICATIONS:
        return

    if notification_service.use_async:
        unbanned_by_id = unbanned_by.pk if unbanned_by else None
        if notification_service._dispatch_async(
            'notify_user_unbanned_task',
            user.pk,
            unbanned_by_id,
            original_ban_reason
        ):
            return

    try:
        if not user.email:
            logger.debug(f"User {user.pk} has no email, skipping unban notification")
            return

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

        logger.info(f"Sent unban notification to user {user.pk}")

    except Exception as exc:
        logger.error(f"Failed to send unban notification: {exc}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
