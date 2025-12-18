"""
GDPR compliance utilities for django-reusable-comments.

Provides functionality for:
- Anonymizing user data in comments
- Data export (Right to Data Portability)
- Data deletion (Right to Erasure)
- Retention policy enforcement

These utilities help ensure compliance with GDPR requirements.
"""

from datetime import timedelta
from typing import Dict, Any
import logging

from django.utils import timezone
from django.conf import settings as django_settings

from .conf import comments_settings
from .utils import get_comment_model

Comment = get_comment_model()
logger = logging.getLogger(comments_settings.LOGGER_NAME)


class GDPRCompliance:
    """
    Utilities for GDPR compliance in comment system.
    
    Provides methods for:
    - Anonymizing personal data
    - Exporting user data
    - Deleting user data
    - Enforcing retention policies
    """
    
    @staticmethod
    def anonymize_ip_address(ip_address: str) -> str:
        """
        Anonymize an IP address for GDPR compliance.
        
        IPv4: 192.168.1.100 -> 192.168.1.0
        IPv6: 2001:0db8:85a3::8a2e:0370:7334 -> 2001:0db8:85a3::
        Empty/None: Returns empty string
        
        Args:
            ip_address: IP address to anonymize
        
        Returns:
            Anonymized IP address or empty string
        
        Example:
            >>> GDPRCompliance.anonymize_ip_address('192.168.1.100')
            '192.168.1.0'
            >>> GDPRCompliance.anonymize_ip_address(None)
            ''
        """
        # FIXED: Return empty string for None or empty input
        if not ip_address:
            return ''
        
        try:
            # Check if IPv6
            if ':' in ip_address:
                # Keep first 3 groups, zero the rest
                parts = ip_address.split(':')
                return ':'.join(parts[:3]) + '::'
            else:
                # IPv4: Keep first 3 octets, zero the last
                parts = ip_address.split('.')
                if len(parts) != 4:
                    return ''
                return '.'.join(parts[:3]) + '.0'
        except Exception as e:
            logger.error(f"Failed to anonymize IP {ip_address}: {e}")
            return ''
    
    @staticmethod
    def anonymize_comment(comment) -> None:
        """
        Anonymize a comment by removing personal data.
        
        Removes:
        - User email
        - IP address (or anonymizes if retention required)
        - User agent
        - Associates with anonymous user
        
        Args:
            comment: Comment instance to anonymize
        
        Example:
            >>> from django_comments.gdpr import GDPRCompliance
            >>> comment = Comment.objects.get(pk=some_id)
            >>> GDPRCompliance.anonymize_comment(comment)
            >>> comment.user_email  # Returns ''
        """
        try:
            # Anonymize or remove IP address based on settings
            if comments_settings.GDPR_ANONYMIZE_IP_ON_RETENTION:
                comment.ip_address = GDPRCompliance.anonymize_ip_address(
                    comment.ip_address or ''
                )
                # FIXED: Set to None if result is empty string
                if not comment.ip_address:
                    comment.ip_address = None
            else:
                comment.ip_address = None
            
            # Remove personal identifiers
            comment.user_email = ''
            comment.user_agent = ''
            comment.user = None  # Disassociate from user account
            
            # Keep user_name if it's generic
            if comment.user_name and '@' in comment.user_name:
                comment.user_name = 'Anonymous'
            
            comment.save(update_fields=[
                'ip_address', 'user_email', 'user_agent', 
                'user', 'user_name', 'updated_at'
            ])
            
            logger.info(f"Anonymized comment {comment.pk}")
            
        except Exception as e:
            logger.error(f"Failed to anonymize comment {comment.pk}: {e}")
            raise
    
    @staticmethod
    def anonymize_user_comments(user) -> int:
        """
        Anonymize all comments by a specific user.
        
        Args:
            user: User instance
        
        Returns:
            Number of comments anonymized
        
        Example:
            >>> from django_comments.gdpr import GDPRCompliance
            >>> user = User.objects.get(username='john')
            >>> count = GDPRCompliance.anonymize_user_comments(user)
            >>> print(f"Anonymized {count} comments")
        """
        comments = Comment.objects.filter(user=user)
        count = comments.count()
        
        for comment in comments:
            GDPRCompliance.anonymize_comment(comment)
        
        logger.info(f"Anonymized {count} comments for user {user.pk}")
        return count
    
    @staticmethod
    def delete_user_data(user, anonymize_comments: bool = True) -> Dict[str, int]:
        """
        Delete or anonymize all user data related to comments.
        
        GDPR "Right to Erasure" implementation.
        
        Args:
            user: User instance
            anonymize_comments: If True, anonymize comments instead of deleting
        
        Returns:
            Dictionary with counts of deleted/anonymized items
        
        Example:
            >>> from django_comments.gdpr import GDPRCompliance
            >>> user = User.objects.get(username='john')
            >>> result = GDPRCompliance.delete_user_data(user)
            >>> print(result)
            {'comments_anonymized': 10, 'flags_deleted': 3, 'bans_deleted': 0}
        """
        from .models import CommentFlag, BannedUser, ModerationAction, CommentRevision
        
        result = {
            'comments_deleted': 0,
            'comments_anonymized': 0,
            'flags_deleted': 0,
            'bans_deleted': 0,
            'moderation_actions_deleted': 0,
            'revisions_deleted': 0,
        }
        
        try:
            # Handle comments
            comments = Comment.objects.filter(user=user)
            comment_count = comments.count()
            
            if anonymize_comments:
                # Anonymize instead of delete to preserve discussions
                result['comments_anonymized'] = GDPRCompliance.anonymize_user_comments(user)
            else:
                # Complete deletion
                comments.delete()
                result['comments_deleted'] = comment_count
            
            # Delete flags created by user
            flags_deleted = CommentFlag.objects.filter(user=user).delete()
            result['flags_deleted'] = flags_deleted[0] if flags_deleted else 0
            
            # Delete bans (user as banned_by)
            # Note: Keep bans where user is the subject for audit trail
            bans_deleted = BannedUser.objects.filter(banned_by=user).update(
                banned_by=None
            )
            result['bans_deleted'] = bans_deleted
            
            # Anonymize moderation actions
            moderation_actions = ModerationAction.objects.filter(
                moderator=user
            ).update(moderator=None)
            result['moderation_actions_deleted'] = moderation_actions
            
            # Delete comment revisions
            revisions_deleted = CommentRevision.objects.filter(
                edited_by=user
            ).delete()
            result['revisions_deleted'] = revisions_deleted[0] if revisions_deleted else 0
            
            logger.info(f"Deleted user data for user {user.pk}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to delete user data for user {user.pk}: {e}")
            raise
    
    @staticmethod
    def export_user_data(user) -> Dict[str, Any]:
        """
        Export all user data for GDPR data portability.
        
        GDPR "Right to Data Portability" implementation.
        
        Args:
            user: User instance
        
        Returns:
            Dictionary with all user data (all dates as ISO strings)
        
        Example:
            >>> from django_comments.gdpr import GDPRCompliance
            >>> user = User.objects.get(username='john')
            >>> data = GDPRCompliance.export_user_data(user)
            >>> # Save to JSON file for user download
        """
        from .models import CommentFlag, BannedUser, ModerationAction, CommentRevision
        
        try:
            # Helper to convert datetime to ISO string
            def to_iso(dt):
                return dt.isoformat() if dt else None
            
            # Export comments with ISO dates
            comments_raw = Comment.objects.filter(user=user).values(
                'id', 'content', 'created_at', 'updated_at', 
                'is_public', 'is_removed', 'user_name', 'user_email',
                'ip_address', 'content_type__model', 'object_id'
            )
            comments = []
            for c in comments_raw:
                comment_dict = dict(c)
                comment_dict['id'] = str(comment_dict['id'])  # Convert UUID to string
                comment_dict['created_at'] = to_iso(comment_dict['created_at'])
                comment_dict['updated_at'] = to_iso(comment_dict['updated_at'])
                comments.append(comment_dict)
            
            # Export flags created by user with ISO dates
            flags_raw = CommentFlag.objects.filter(user=user).values(
                'id', 'flag', 'reason', 'created_at',
                'comment_type__model', 'comment_id'
            )
            flags = []
            for f in flags_raw:
                flag_dict = dict(f)
                flag_dict['id'] = str(flag_dict['id'])
                flag_dict['flag_type'] = flag_dict.pop('flag')  # Rename 'flag' to 'flag_type'
                flag_dict['created_at'] = to_iso(flag_dict['created_at'])
                flags.append(flag_dict)
            
            # Export bans received by user with ISO dates and is_active
            bans_raw = BannedUser.objects.filter(user=user).select_related('banned_by')
            bans = []
            for ban in bans_raw:
                ban_dict = {
                    'reason': ban.reason,
                    'created_at': to_iso(ban.created_at),
                    'banned_until': to_iso(ban.banned_until),
                    'is_active': ban.is_active,  # Property method
                    'banned_by': ban.banned_by.get_username() if ban.banned_by else None,
                }
                bans.append(ban_dict)
            
            # Export moderation actions performed by user
            actions_raw = ModerationAction.objects.filter(
                moderator=user
            ).values('action', 'reason', 'timestamp')
            actions = []
            for a in actions_raw:
                action_dict = dict(a)
                action_dict['timestamp'] = to_iso(action_dict['timestamp'])
                actions.append(action_dict)
            
            # Export comment revisions created by user
            revisions_raw = CommentRevision.objects.filter(
                edited_by=user
            ).values('content', 'edited_at', 'comment_id')
            revisions = []
            for r in revisions_raw:
                revision_dict = dict(r)
                revision_dict['edited_at'] = to_iso(revision_dict['edited_at'])
                revision_dict['comment_id'] = str(revision_dict['comment_id'])
                revisions.append(revision_dict)
            
            # Calculate statistics
            stats = {
                'total_comments': len(comments),
                'total_flags_created': len(flags),
                'total_bans_received': len(bans),
                'total_moderation_actions': len(actions),
                'total_revisions': len(revisions),
            }
            
            data = {
                'export_date': timezone.now().isoformat(),
                'user': {
                    'id': str(user.pk),
                    'username': user.get_username(),
                    'email': user.email if hasattr(user, 'email') else '',
                },
                'comments': comments,
                'flags_created': flags,
                'bans_received': bans,
                'moderation_actions': actions,
                'comment_revisions': revisions,
                'statistics': stats,
            }
            
            logger.info(f"Exported data for user {user.pk}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to export data for user {user.pk}: {e}")
            raise
    
    @staticmethod
    def enforce_retention_policy(
        retention_policy_enabled: bool = None,
        retention_days: int = None,
        anonymize_ip: bool = None
    ) -> Dict[str, Any]:
        """
        Enforce data retention policy by anonymizing old personal data.
        
        GDPR retention compliance implementation.
        Should be run periodically (e.g., via cron job or celery task).
        
        Args:
            retention_policy_enabled: Whether retention policy is enabled (defaults to settings)
            retention_days: Number of days to retain data (defaults to settings)
            anonymize_ip: Whether to anonymize IPs instead of removing (defaults to settings)
        
        Returns:
            Dictionary with counts of anonymized items
        
        Example:
            # In management command or celery task
            >>> from django_comments.gdpr import GDPRCompliance
            >>> result = GDPRCompliance.enforce_retention_policy(
            ...     retention_policy_enabled=True,
            ...     retention_days=365
            ... )
            >>> print(f"Anonymized {result['comments_anonymized']} comments")
        """
        # Use provided parameters or fall back to settings
        if retention_policy_enabled is None:
            retention_policy_enabled = comments_settings.GDPR_ENABLE_RETENTION_POLICY
        
        if retention_days is None:
            retention_days = comments_settings.GDPR_RETENTION_DAYS
        
        if anonymize_ip is None:
            anonymize_ip = comments_settings.GDPR_ANONYMIZE_IP_ON_RETENTION
        
        if not retention_policy_enabled:
            logger.info("Retention policy is disabled")
            return {
                'comments_anonymized': 0,
                'cutoff_date': None,
                'retention_days': None
            }
        
        if not retention_days:
            logger.warning("Retention policy enabled but GDPR_RETENTION_DAYS not set")
            return {
                'comments_anonymized': 0,
                'cutoff_date': None,
                'retention_days': retention_days
            }
        
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        # FIXED: Use < for "older than X days" (strictly greater)
        # Comment at exactly retention_days should NOT be anonymized
        old_comments = Comment.objects.filter(
            created_at__lt=cutoff_date
        ).exclude(
            user__isnull=True,
            user_email='',
            ip_address__isnull=True
        )
        
        count = 0
        for comment in old_comments:
            try:
                # Temporarily override the IP anonymization setting if provided
                if anonymize_ip is not None:
                    original_setting = comments_settings.GDPR_ANONYMIZE_IP_ON_RETENTION
                    comments_settings.GDPR_ANONYMIZE_IP_ON_RETENTION = anonymize_ip
                    
                GDPRCompliance.anonymize_comment(comment)
                count += 1
                
                # Restore original setting
                if anonymize_ip is not None:
                    comments_settings.GDPR_ANONYMIZE_IP_ON_RETENTION = original_setting
                    
            except Exception as e:
                logger.error(f"Failed to anonymize comment {comment.pk}: {e}")
        
        logger.info(f"Retention policy: Anonymized {count} comments older than {retention_days} days")
        
        return {
            'comments_anonymized': count,
            'cutoff_date': cutoff_date.isoformat(),
            'retention_days': retention_days,
        }


# Convenience functions for quick access

def anonymize_comment(comment) -> None:
    """Anonymize a single comment."""
    return GDPRCompliance.anonymize_comment(comment)


def anonymize_user_comments(user) -> int:
    """Anonymize all comments by a user."""
    return GDPRCompliance.anonymize_user_comments(user)


def delete_user_data(user, anonymize_comments: bool = True) -> Dict[str, int]:
    """Delete all user data (GDPR Right to Erasure)."""
    return GDPRCompliance.delete_user_data(user, anonymize_comments)


def export_user_data(user) -> Dict[str, Any]:
    """Export all user data (GDPR Right to Data Portability)."""
    return GDPRCompliance.export_user_data(user)


def enforce_retention_policy(**kwargs) -> Dict[str, int]:
    """Enforce data retention policy."""
    return GDPRCompliance.enforce_retention_policy(**kwargs)