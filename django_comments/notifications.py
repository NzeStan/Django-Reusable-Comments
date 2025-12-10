"""
Email notification system for django-reusable-comments.

Supports both synchronous (default) and asynchronous (Celery) email sending.

To enable async notifications:
1. Install celery: pip install celery
2. Set DJANGO_COMMENTS['USE_ASYNC_NOTIFICATIONS'] = True
3. Start Celery workers

Notifications will gracefully fall back to synchronous sending if Celery is not available.
"""
import logging
from typing import List, Optional
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.sites.models import Site
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .conf import comments_settings

logger = logging.getLogger(comments_settings.LOGGER_NAME)


class CommentNotificationService:
    """Service for sending comment notifications (sync or async)."""
    
    def __init__(self):
        self.enabled = comments_settings.SEND_NOTIFICATIONS
        self.from_email = comments_settings.DEFAULT_FROM_EMAIL
        self.use_async = comments_settings.USE_ASYNC_NOTIFICATIONS
        
        # Check if Celery is actually available when async is enabled
        if self.use_async:
            try:
                from . import tasks
                self._tasks_available = hasattr(tasks, 'CELERY_AVAILABLE') and tasks.CELERY_AVAILABLE
                if not self._tasks_available:
                    logger.warning(
                        "USE_ASYNC_NOTIFICATIONS is True but Celery is not installed. "
                        "Falling back to synchronous notifications. "
                        "Install celery: pip install celery"
                    )
            except ImportError:
                self._tasks_available = False
                logger.warning(
                    "USE_ASYNC_NOTIFICATIONS is True but tasks module failed to import. "
                    "Falling back to synchronous notifications."
                )
        else:
            self._tasks_available = False
    
    def _dispatch_async(self, task_name: str, *args, **kwargs):
        """
        Dispatch a task to Celery if available, otherwise execute synchronously.
        
        Args:
            task_name: Name of the task to execute
            *args, **kwargs: Arguments to pass to the task
        """
        if not self.use_async or not self._tasks_available:
            return False
        
        try:
            from . import tasks
            task_func = getattr(tasks, task_name, None)
            if task_func and callable(task_func):
                # Call .delay() to execute asynchronously
                task_func.delay(*args, **kwargs)
                logger.debug(f"Dispatched async task: {task_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to dispatch async task {task_name}: {e}. Falling back to sync.")
        
        return False
    
    def notify_new_comment(self, comment):
        """
        Notify about a new comment.
        
        Args:
            comment: Comment instance
        """
        if not self.enabled:
            return
        
        # Try async dispatch
        if self._dispatch_async('notify_new_comment_task', str(comment.pk)):
            return
        
        # Fall back to synchronous
        try:
            # Get recipients
            recipients = self._get_comment_recipients(comment)
            
            if not recipients:
                logger.debug(f"No recipients for comment {comment.pk}")
                return
            
            # Prepare context
            context = self._get_notification_context(comment)
            
            # Get subject
            subject = comments_settings.NOTIFICATION_SUBJECT.format(
                object=str(comment.content_object)
            )
            
            # Send email
            self._send_notification_email(
                recipients=recipients,
                subject=subject,
                template=comments_settings.NOTIFICATION_EMAIL_TEMPLATE,
                context=context
            )
            
            logger.info(f"Sent new comment notification for comment {comment.pk} to {len(recipients)} recipients")
            
        except Exception as e:
            logger.error(f"Failed to send notification for comment {comment.pk}: {e}")
    
    def notify_comment_reply(self, comment, parent_comment):
        """
        Notify about a reply to a comment.
        
        Args:
            comment: The reply comment
            parent_comment: The parent comment being replied to
        """
        if not self.enabled:
            return
        
        # Try async dispatch
        if self._dispatch_async('notify_comment_reply_task', str(comment.pk), str(parent_comment.pk)):
            return
        
        # Fall back to synchronous
        try:
            # Notify parent comment author
            if parent_comment.user and parent_comment.user.email:
                recipients = [parent_comment.user.email]
            elif parent_comment.user_email:
                recipients = [parent_comment.user_email]
            else:
                return
            
            # Don't notify if replying to own comment
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
            
        except Exception as e:
            logger.error(f"Failed to send reply notification: {e}")
    
    def notify_comment_approved(self, comment, moderator=None):
        """
        Notify comment author that their comment was approved.
        
        Args:
            comment: Comment instance
            moderator: User who approved the comment
        """
        if not self.enabled:
            return
        
        # Try async dispatch
        moderator_id = moderator.pk if moderator else None
        if self._dispatch_async('notify_comment_approved_task', str(comment.pk), moderator_id):
            return
        
        # Fall back to synchronous
        try:
            # Get author email
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
            
        except Exception as e:
            logger.error(f"Failed to send approval notification: {e}")
    
    def notify_comment_rejected(self, comment, moderator=None):
        """
        Notify comment author that their comment was rejected.
        
        Args:
            comment: Comment instance
            moderator: User who rejected the comment
        """
        if not self.enabled:
            return
        
        # Try async dispatch
        moderator_id = moderator.pk if moderator else None
        if self._dispatch_async('notify_comment_rejected_task', str(comment.pk), moderator_id):
            return
        
        # Fall back to synchronous
        try:
            # Get author email
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
            
        except Exception as e:
            logger.error(f"Failed to send rejection notification: {e}")
    
    def notify_moderators(self, comment):
        """
        Notify moderators about a new comment that needs approval.
        
        Args:
            comment: Comment instance
        """
        if not self.enabled:
            return
        
        # Try async dispatch
        if self._dispatch_async('notify_moderators_task', str(comment.pk)):
            return
        
        # Fall back to synchronous
        try:
            # Get moderator emails
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
            
        except Exception as e:
            logger.error(f"Failed to send moderator notification: {e}")
    
    def _get_comment_recipients(self, comment) -> List[str]:
        """
        Get list of email addresses to notify about a comment.
        Override this method to customize recipient logic.
        """
        recipients = []
        
        # Strategy 1: Notify content object owner if they have email
        if hasattr(comment.content_object, 'author'):
            author = comment.content_object.author
            if hasattr(author, 'email') and author.email:
                recipients.append(author.email)
        elif hasattr(comment.content_object, 'user'):
            user = comment.content_object.user
            if hasattr(user, 'email') and user.email:
                recipients.append(user.email)
        
        # Strategy 2: Use configured notification emails
        notification_emails = comments_settings.COMMENT_NOTIFICATION_EMAILS
        recipients.extend(notification_emails)
        
        # Remove duplicates and exclude comment author
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
        
        # Get emails from users with moderation permission
        moderators = User.objects.filter(
            groups__permissions__codename='can_moderate_comments'
        ).distinct()
        
        emails = [u.email for u in moderators if u.email]
        
        # Also check for staff users
        staff = User.objects.filter(is_staff=True).distinct()
        emails.extend([u.email for u in staff if u.email and u.email not in emails])
        
        return emails
    
    def _get_notification_context(self, comment) -> dict:
        """
        Build context dictionary for email templates.
        
        ✅ FIXED: Now handles None comment for ban notifications.
        
        Args:
            comment: Comment instance or None (for ban notifications)
        
        Returns:
            dict: Context for email template
        """
        # Try to get site info
        try:
            site = Site.objects.get_current()
            domain = site.domain
            site_name = site.name
        except Exception:
            # Fallback to configured values
            domain = comments_settings.SITE_DOMAIN or 'example.com'
            site_name = comments_settings.SITE_NAME or 'Our Site'
        
        protocol = 'https' if comments_settings.USE_HTTPS else 'http'
        
        # ✅ FIXED: Build base context without comment-specific fields
        context = {
            'site_name': site_name,
            'domain': domain,
            'protocol': protocol,
        }
        
        # ✅ FIXED: Only add comment fields if comment is provided
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
            # Render email body
            html_body = render_to_string(template, context)
            
            # Try to render plain text version
            text_template = template.replace('.html', '.txt')
            try:
                text_body = render_to_string(text_template, context)
            except Exception:
                # If no text template, create simple version from HTML
                import re
                text_body = re.sub('<[^<]+?>', '', html_body)
            
            # Send email
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=self.from_email,
                to=recipients
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=False)
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
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
    
    # Try async dispatch
    if notification_service.use_async and notification_service._tasks_available:
        if notification_service._dispatch_async(
            'notify_moderators_of_flag_task',
            str(comment.pk),
            str(flag.pk),
            flag_count
        ):
            return
    
    # Fall back to synchronous
    try:
        # Get moderator emails
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
        
    except Exception as e:
        logger.error(f"Failed to send flag notification: {e}")


def notify_auto_hide(comment, flag_count):
    """
    Notify moderators that a comment was auto-hidden.
    
    Args:
        comment: Comment instance
        flag_count: Number of flags that triggered auto-hide
    """
    if not comments_settings.SEND_NOTIFICATIONS or not comments_settings.NOTIFY_ON_AUTO_HIDE:
        return
    
    # Try async dispatch
    if notification_service.use_async and notification_service._tasks_available:
        if notification_service._dispatch_async('notify_auto_hide_task', str(comment.pk), flag_count):
            return
    
    # Fall back to synchronous
    try:
        recipients = notification_service._get_moderator_emails()
        
        if not recipients:
            return
        
        context = notification_service._get_notification_context(comment)
        context['flag_count'] = flag_count
        context['threshold'] = comments_settings.AUTO_HIDE_THRESHOLD
        context['auto_action'] = 'hidden'
        
        subject = _("Comment auto-hidden after {count} flags").format(count=flag_count)
        
        # Use moderator template (can be customized later)
        notification_service._send_notification_email(
            recipients=recipients,
            subject=subject,
            template=comments_settings.NOTIFICATION_MODERATOR_TEMPLATE,
            context=context
        )
        
        logger.info(f"Sent auto-hide notification for comment {comment.pk}")
        
    except Exception as e:
        logger.error(f"Failed to send auto-hide notification: {e}")


def notify_user_banned(ban):
    """
    Notify user that they have been banned.
    
    ✅ FIXED: Now properly handles ban context without comment.
    
    Args:
        ban: BannedUser instance
    """
    if not comments_settings.SEND_NOTIFICATIONS:
        return
    
    # Try async dispatch
    if notification_service.use_async and notification_service._tasks_available:
        if notification_service._dispatch_async('notify_user_banned_task', str(ban.pk)):
            return
    
    # Fall back to synchronous
    try:
        if not ban.user.email:
            logger.debug(f"User {ban.user.pk} has no email, skipping ban notification")
            return
        
        recipients = [ban.user.email]
        
        context = notification_service._get_notification_context(None)
        
        # Add ban-specific context
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
        
    except Exception as e:
        logger.error(f"Failed to send ban notification: {e}")
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
    
    # Try async dispatch
    if notification_service.use_async and notification_service._tasks_available:
        unbanned_by_id = unbanned_by.pk if unbanned_by else None
        if notification_service._dispatch_async(
            'notify_user_unbanned_task',
            user.pk,
            unbanned_by_id,
            original_ban_reason
        ):
            return
    
    # Fall back to synchronous
    try:
        if not user.email:
            logger.debug(f"User {user.pk} has no email, skipping unban notification")
            return
        
        recipients = [user.email]
        
        context = notification_service._get_notification_context(None)
        
        # Add unban-specific context
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
        
    except Exception as e:
        logger.error(f"Failed to send unban notification: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")