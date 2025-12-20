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


"""
TRULY FINAL VERSION of trigger_notifications function for django_comments/signals.py

The issue: CommentsSettings has a custom __getattr__ that reads from Django settings,
so patch.object doesn't work as expected. 

The solution: Read from comments_settings FIRST (this gets the patched value when 
patch.object is used), then check if Django settings has an explicit override 
(for @override_settings support).

Replace your existing trigger_notifications function with this entire function.
"""


def trigger_notifications(comment, created=False):
    """
    Trigger email notifications based on comment state.
    Called after a comment is saved.
    
    Args:
        comment: Comment instance
        created: Whether this is a new comment
    """
    from django.conf import settings as django_settings
    
    # CRITICAL: Start with comments_settings (respects patch.object due to __getattr__)
    # When patch.object is used, it sets an instance attribute that Python finds
    # before calling __getattr__, so this works!
    send_notifications = comments_settings.SEND_NOTIFICATIONS
    
    # Then check if Django settings has an explicit override (for @override_settings)
    # Check COMMENTS first (used in tests)
    comments_config = getattr(django_settings, 'COMMENTS', None)
    if comments_config and isinstance(comments_config, dict) and 'SEND_NOTIFICATIONS' in comments_config:
        send_notifications = comments_config['SEND_NOTIFICATIONS']
    else:
        # Check DJANGO_COMMENTS (alternative setting name)
        comments_config = getattr(django_settings, 'DJANGO_COMMENTS', None)
        if comments_config and isinstance(comments_config, dict) and 'SEND_NOTIFICATIONS' in comments_config:
            send_notifications = comments_config['SEND_NOTIFICATIONS']
    
    # Only send notifications if enabled
    if not send_notifications:
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
            # Use same pattern: comments_settings first, then Django settings override
            moderator_required = comments_settings.MODERATOR_REQUIRED
            
            comments_config = getattr(django_settings, 'COMMENTS', None)
            if comments_config and isinstance(comments_config, dict) and 'MODERATOR_REQUIRED' in comments_config:
                moderator_required = comments_config['MODERATOR_REQUIRED']
            else:
                comments_config = getattr(django_settings, 'DJANGO_COMMENTS', None)
                if comments_config and isinstance(comments_config, dict) and 'MODERATOR_REQUIRED' in comments_config:
                    moderator_required = comments_config['MODERATOR_REQUIRED']
            
            if moderator_required and not comment.is_public:
                notify_moderators(comment)
                
    except Exception as e:
        # Log error but don't break the save process
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
    Flag a comment with proper UUID handling and duplicate prevention.
    
    CRITICAL FIXES:
    1. Check for existing flags before creating to prevent IntegrityError
    2. Raise ValidationError for duplicates (handled by view as 400 response)
    3. Proper UUID-to-string conversion for GenericForeignKey compatibility
    4. Check auto-ban conditions after flagging
    5. Auto-ban user if conditions are met
    
    The database has a UNIQUE constraint on (comment_type, comment_id, user, flag).
    Instead of letting the database raise IntegrityError (which becomes a 500 error),
    we check for existing flags first and raise ValidationError (becomes 400 error).
    
    This matches the test expectations where duplicate flags should return:
    - HTTP 400 Bad Request
    - {"detail": "You have already flagged this comment with this flag type"}
    
    NOT a 500 Internal Server Error with IntegrityError.
    
    Args:
        comment: Comment instance to flag
        user: User creating the flag
        flag: Flag type (default: 'other')
        reason: Optional reason for the flag
    
    Returns:
        CommentFlag: The created flag object
    
    Raises:
        ValidationError: If user has already flagged this comment with this flag type
        ValueError: If comment or user is invalid
    
    Example:
        >>> try:
        ...     flag = flag_comment(comment, user, flag='spam', reason='This is spam')
        ... except ValidationError as e:
        ...     # Handle duplicate flag - return 400 to user
        ...     return Response({'detail': str(e)}, status=400)
    
    Side Effects:
        - Creates a CommentFlag object
        - Logs moderation action
        - Sends comment_flagged signal
        - Checks if comment should be auto-hidden
        - Notifies moderators if flag threshold reached
        - Checks if user should be auto-banned
        - Auto-bans user if conditions are met
    """
    from django.core.exceptions import ValidationError
    from django.contrib.contenttypes.models import ContentType
    from django_comments.utils import get_comment_model
    
    Comment = get_comment_model()
    
    # Validate inputs
    if not isinstance(comment, Comment):
        raise ValueError("comment must be a Comment instance")
    
    if not user or not user.is_authenticated:
        raise ValueError("user must be an authenticated user")
    
    # Get content type for comment
    comment_ct = ContentType.objects.get_for_model(comment)
    
    # =========================================================================
    # Check for duplicate flags
    # =========================================================================
    existing_flag = CommentFlag.objects.filter(
        comment_type=comment_ct,
        comment_id=str(comment.pk),  # Convert UUID to string
        user=user,
        flag=flag
    ).first()
    
    if existing_flag:
        # User has already flagged this comment with this flag type
        raise ValidationError(
            f"You have already flagged this comment as '{flag}'. "
            "You cannot flag the same comment multiple times with the same flag type."
        )
    
    # =========================================================================
    # Create the flag with proper UUID-to-string conversion
    # =========================================================================
    flag_obj = CommentFlag.objects.create(
        comment_type=comment_ct,
        comment_id=str(comment.pk),  # CRITICAL: Always convert to string
        user=user,
        flag=flag,
        reason=reason
    )
    
    # =========================================================================
    # Log moderation action
    # =========================================================================
    log_moderation_action(
        comment=comment,
        moderator=user,
        action='flagged',
        reason=f"Flagged as {flag}: {reason}" if reason else f"Flagged as {flag}"
    )
    
    # =========================================================================
    # Send signal
    # =========================================================================
    safe_send(
        comment_flagged,
        sender=CommentFlag,
        flag=flag_obj,
        comment=comment,
        user=user,
        flag_type=flag,
        reason=reason
    )
    
    # =========================================================================
    # Check if comment should be auto-hidden based on flag count
    # AND notify moderators if flag threshold is reached
    # =========================================================================
    try:
        from django_comments.utils import check_flag_threshold
        threshold_result = check_flag_threshold(comment)
    except Exception as e:
        logger.error(f"Error checking flag threshold: {e}")
        threshold_result = {}
    
    # =========================================================================
    # Check if comment author should be auto-banned
    # =========================================================================
    try:
        from django_comments.utils import check_auto_ban_conditions, auto_ban_user
        
        should_ban, ban_reason = check_auto_ban_conditions(comment.user)
        if should_ban:
            auto_ban_user(comment.user, ban_reason)
    except Exception as e:
        logger.error(f"Error checking auto-ban conditions: {e}")
    
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
