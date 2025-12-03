from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import receiver, Signal
from .utils import get_comment_model

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


# Comment lifecycle signal forwarding
@receiver(pre_save, sender=Comment)
def on_comment_pre_save(sender, instance, **kwargs):
    safe_send(comment_pre_save, sender=sender, comment=instance, **kwargs)


@receiver(post_save, sender=Comment)
def on_comment_post_save(sender, instance, created, **kwargs):
    """
    Handle comment post-save.
    IMPROVED: Now applies automatic flags for spam/profanity on creation.
    """
    safe_send(comment_post_save, sender=sender, comment=instance, created=created, **kwargs)
    
    # Apply automatic flags for new comments if needed
    if created:
        from .utils import apply_automatic_flags
        try:
            apply_automatic_flags(instance)
        except Exception as e:
            import logging
            from .conf import comments_settings
            logger = logging.getLogger(comments_settings.LOGGER_NAME)
            logger.error(f"Failed to apply automatic flags to comment {instance.pk}: {e}")


@receiver(pre_delete, sender=Comment)
def on_comment_pre_delete(sender, instance, **kwargs):
    safe_send(comment_pre_delete, sender=sender, comment=instance, **kwargs)


@receiver(post_delete, sender=Comment)
def on_comment_post_delete(sender, instance, **kwargs):
    safe_send(comment_post_delete, sender=sender, comment=instance, **kwargs)


def flag_comment(comment, user, flag='other', reason=''):
    """
    Flag a comment and send a signal.
    
    Args:
        comment: Comment or UUIDComment instance
        user: User who is flagging
        flag: Flag type (default: 'other')
        reason: Optional reason
    
    Returns:
        CommentFlag instance
    
    Example:
        from django_comments.signals import flag_comment
        
        flag = flag_comment(
            comment=my_comment,
            user=request.user,
            flag='spam',
            reason='This is clearly spam'
        )
    """
    from .models import CommentFlag
    
    # Use manager method for safe creation
    comment_flag, created = CommentFlag.objects.create_or_get_flag(
        comment=comment,
        user=user,
        flag=flag,
        reason=reason
    )
    
    # Send signal only if newly created
    if created:
        safe_send(
            comment_flagged,
            sender=CommentFlag,
            flag=comment_flag,
            comment=comment,
            user=user,
            flag_type=flag,
            reason=reason
        )
    
    return comment_flag


def approve_comment(comment, moderator=None):
    """
    Approve a comment and send a signal.
    """
    if not comment.is_public:
        comment.is_public = True
        comment.save(update_fields=['is_public'])

        safe_send(
            comment_approved,
            sender=comment.__class__,
            comment=comment,
            moderator=moderator
        )

    return comment


def reject_comment(comment, moderator=None):
    """
    Reject a comment and send a signal.
    """
    if comment.is_public:
        comment.is_public = False
        comment.save(update_fields=['is_public'])

        safe_send(
            comment_rejected,
            sender=comment.__class__,
            comment=comment,
            moderator=moderator
        )

    return comment