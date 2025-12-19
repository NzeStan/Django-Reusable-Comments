import logging

from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import receiver, Signal
from django.contrib.contenttypes.models import ContentType
from django_comments.conf import comments_settings
from django_comments.models import CommentFlag
from django_comments.utils import log_moderation_action
from .conf import comments_settings as local_comments_settings
from .utils import get_comment_model
logger = logging.getLogger(comments_settings.LOGGER_NAME)


Comment = get_comment_model()

# Custom signals
comment_pre_save = Signal()
comment_post_save = Signal()
comment_pre_delete = Signal()
comment_post_delete = Signal()

# Moderation signals
comment_flagged = Signal()
comment_approved = Signal()
comment_rejected = Signal()


def safe_send(signal_obj, sender, **extra_kwargs):
    """Safely send a signal, avoiding duplicate 'signal' keyword errors."""
    extra_kwargs.pop("signal", None)
    signal_obj.send(sender=sender, **extra_kwargs)


def trigger_notifications(comment, created=False):
    """
    Trigger email notifications based on comment state.
    Called after a comment is saved.
    
    Args:
        comment: Comment instance
        created: Whether this is a new comment
    """
    # Only send notifications if enabled
    if not comments_settings.SEND_NOTIFICATIONS:
        return
    
    # Import here to avoid circular imports
    from .notifications import (
        notify_new_comment,
        notify_comment_reply,
        notify_moderators,
    )
    
    try:
        # For new comments
        if created:
            # 1. Notify content owner about new comment
            notify_new_comment(comment)
            
            # 2. If it's a reply, notify parent comment author
            if comment.parent:
                notify_comment_reply(comment, parent_comment=comment.parent)
            
            # 3. If moderation is required, notify moderators
            if comments_settings.MODERATOR_REQUIRED and not comment.is_public:
                notify_moderators(comment)
                
    except Exception as e:
        # Log error but don't break the save process
        import logging
        logger = logging.getLogger(comments_settings.LOGGER_NAME)
        logger.error(f"Failed to send notification for comment {comment.pk}: {e}")


# Comment lifecycle signal forwarding
@receiver(pre_save, sender=Comment)
def on_comment_pre_save(sender, instance, **kwargs):
    """Handle comment pre-save."""
    safe_send(comment_pre_save, sender=sender, comment=instance, **kwargs)


@receiver(post_save, sender=Comment)
def on_comment_post_save(sender, instance, created, **kwargs):
    """
    Handle comment post-save.
    Triggers automatic flagging and email notifications.
    """
    # Send custom signal
    safe_send(comment_post_save, sender=sender, comment=instance, created=created, **kwargs)
    
    # Apply automatic flags for new comments if needed
    if created:
        from .utils import apply_automatic_flags
        try:
            apply_automatic_flags(instance)
        except Exception as e:
            import logging
            logger = logging.getLogger(comments_settings.LOGGER_NAME)
            logger.error(f"Failed to apply automatic flags to comment {instance.pk}: {e}")
    
    # Trigger email notifications
    trigger_notifications(instance, created=created)


@receiver(pre_delete, sender=Comment)
def on_comment_pre_delete(sender, instance, **kwargs):
    """Handle comment pre-delete."""
    safe_send(comment_pre_delete, sender=sender, comment=instance, **kwargs)


@receiver(post_delete, sender=Comment)
def on_comment_post_delete(sender, instance, **kwargs):
    """Handle comment post-delete."""
    safe_send(comment_post_delete, sender=sender, comment=instance, **kwargs)


def flag_comment(comment, user, flag='other', reason=''):
    """
    FIXED: Flag a comment and send a signal with proper UUID handling.
    
    Replace your flag_comment() function in signals.py with this complete function.
    
    Args:
        comment: Comment instance to flag
        user: User who is flagging
        flag: Flag type (default: 'other')
        reason: Optional reason for flagging
    
    Returns:
        CommentFlag instance
    """
    from django.contrib.contenttypes.models import ContentType
    from django_comments.models import CommentFlag
    from django_comments.utils import log_moderation_action
    from django_comments.signals import comment_flagged, safe_send
    import logging
    from django_comments.conf import comments_settings
    
    logger = logging.getLogger(comments_settings.LOGGER_NAME)
    
    # CRITICAL FIX: Convert comment PK to string for proper matching
    comment_ct = ContentType.objects.get_for_model(comment)
    
    # Create the flag with proper UUID-to-string conversion
    flag_obj = CommentFlag.objects.create(
        comment_type=comment_ct,
        comment_id=str(comment.pk),  # CRITICAL: Always convert to string
        user=user,
        flag=flag,
        reason=reason
    )
    
    # Log moderation action
    log_moderation_action(
        comment=comment,
        moderator=user,
        action='flagged',
        reason=f"Flagged as {flag}: {reason}" if reason else f"Flagged as {flag}"
    )
    
    # Send signal
    safe_send(
        comment_flagged,
        sender=CommentFlag,
        flag=flag_obj,
        comment=comment,
        user=user,
        flag_type=flag,
        reason=reason
    )
    
    # Check if comment should be auto-hidden based on flag count
    from django_comments.utils import check_flag_threshold
    try:
        check_flag_threshold(comment)
    except Exception as e:
        logger.error(f"Error checking flag threshold: {e}")
    
    return flag_obj




def approve_comment(comment, moderator=None):
    """
    Approve a comment and send a signal.
    Also triggers email notification to comment author.
    
    Args:
        comment: Comment instance
        moderator: User who approved the comment
    
    Returns:
        Comment instance
    """
    if not comment.is_public:
        comment.is_public = True
        comment.save(update_fields=['is_public'])

        # Send approval signal
        safe_send(
            comment_approved,
            sender=comment.__class__,
            comment=comment,
            moderator=moderator
        )
        
        # Send email notification to comment author
        if comments_settings.SEND_NOTIFICATIONS:
            from .notifications import notify_comment_approved
            try:
                notify_comment_approved(comment, moderator=moderator)
            except Exception as e:
                import logging
                logger = logging.getLogger(comments_settings.LOGGER_NAME)
                logger.error(f"Failed to send approval notification for comment {comment.pk}: {e}")

    return comment


def reject_comment(comment, moderator=None):
    """
    Reject a comment and send a signal.
    Also triggers email notification to comment author.
    
    Args:
        comment: Comment instance
        moderator: User who rejected the comment
    
    Returns:
        Comment instance
    """
    if comment.is_public:
        comment.is_public = False
        comment.save(update_fields=['is_public'])

        # Send rejection signal
        safe_send(
            comment_rejected,
            sender=comment.__class__,
            comment=comment,
            moderator=moderator
        )
        
        # Send email notification to comment author
        if comments_settings.SEND_NOTIFICATIONS:
            from .notifications import notify_comment_rejected
            try:
                notify_comment_rejected(comment, moderator=moderator)
            except Exception as e:
                import logging
                logger = logging.getLogger(comments_settings.LOGGER_NAME)
                logger.error(f"Failed to send rejection notification for comment {comment.pk}: {e}")

    return comment
