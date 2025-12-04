"""
Notification system for django-comments.
Handles email notifications for new comments, replies, and moderation events.
"""
import logging
from typing import List, Optional
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.sites.models import Site
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from .conf import comments_settings

logger = logging.getLogger(comments_settings.LOGGER_NAME)


class CommentNotificationService:
    """Service for sending comment notifications."""
    
    def __init__(self):
        self.enabled = comments_settings.SEND_NOTIFICATIONS
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
    
    def notify_new_comment(self, comment):
        """
        Notify about a new comment.
        
        Args:
            comment: Comment instance
        """
        if not self.enabled:
            return
        
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
        notification_emails = getattr(
            settings,
            'COMMENT_NOTIFICATION_EMAILS',
            []
        )
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
        """Build context dictionary for email templates."""
        try:
            site = Site.objects.get_current()
            domain = site.domain
            site_name = site.name
        except Exception:
            domain = getattr(settings, 'SITE_DOMAIN', 'example.com')
            site_name = getattr(settings, 'SITE_NAME', 'Our Site')
        
        return {
            'comment': comment,
            'content_object': comment.content_object,
            'site_name': site_name,
            'domain': domain,
            'protocol': 'https' if getattr(settings, 'USE_HTTPS', True) else 'http',
        }
    
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


# Convenience functions
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