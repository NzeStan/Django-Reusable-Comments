"""
GDPR Compliance Utilities
==========================

Provides utilities for handling personal data in compliance with GDPR regulations.

Features:
- Data anonymization
- Data export
- Data deletion
- Consent tracking
- Retention policy enforcement
"""

import logging
from datetime import timedelta
from typing import List, Dict, Any, Optional
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from .conf import comments_settings
from .utils import get_comment_model

User = get_user_model()
Comment = get_comment_model()
logger = logging.getLogger(comments_settings.LOGGER_NAME)


class GDPRCompliance:
    """
    Handle GDPR compliance for comment system.
    
    Key principles:
    - Data minimization
    - Storage limitation
    - Purpose limitation
    - Right to erasure
    - Right to data portability
    """
    
    @staticmethod
    def anonymize_ip_address(ip_address: str) -> str:
        """
        Anonymize IP address by zeroing last octet (IPv4) or last 80 bits (IPv6).
        
        This maintains geographic information while protecting user identity.
        
        Examples:
            192.168.1.100 -> 192.168.1.0
            2001:0db8:85a3:0000:0000:8a2e:0370:7334 -> 2001:0db8:85a3:0000:0000::
        
        Args:
            ip_address: Full IP address
        
        Returns:
            Anonymized IP address
        """
        if not ip_address:
            return ''
        
        try:
            if ':' in ip_address:  # IPv6
                # Keep first 48 bits (network prefix), zero the rest
                parts = ip_address.split(':')
                return ':'.join(parts[:3]) + ':0000:0000:0000:0000:0000'
            else:  # IPv4
                # Zero the last octet
                parts = ip_address.split('.')
                return '.'.join(parts[:3]) + '.0'
        except Exception as e:
            logger.error(f"Failed to anonymize IP {ip_address}: {e}")
            return '0.0.0.0'
    
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
            Dictionary containing all user data
        
        Example:
            >>> from django_comments.gdpr import GDPRCompliance
            >>> import json
            >>> user = User.objects.get(username='john')
            >>> data = GDPRCompliance.export_user_data(user)
            >>> with open('user_data.json', 'w') as f:
            >>>     json.dump(data, f, indent=2, default=str)
        """
        from .models import CommentFlag, BannedUser, ModerationAction, CommentRevision
        from django.contrib.contenttypes.models import ContentType
        
        try:
            # Export comments
            comments = Comment.objects.filter(user=user).select_related(
                'content_type', 'parent'
            )
            comments_data = []
            
            for comment in comments:
                comments_data.append({
                    'id': str(comment.pk),
                    'content': comment.content,
                    'created_at': comment.created_at.isoformat(),
                    'updated_at': comment.updated_at.isoformat(),
                    'is_public': comment.is_public,
                    'is_removed': comment.is_removed,
                    'commented_on': {
                        'type': f"{comment.content_type.app_label}.{comment.content_type.model}",
                        'id': comment.object_id,
                        'repr': str(comment.content_object) if comment.content_object else None,
                    },
                    'parent_id': str(comment.parent.pk) if comment.parent else None,
                    'ip_address': comment.ip_address,
                    'user_agent': comment.user_agent,
                })
            
            # Export flags created by user
            flags = CommentFlag.objects.filter(user=user).select_related(
                'comment_type'
            )
            flags_data = []
            
            for flag in flags:
                flags_data.append({
                    'id': str(flag.pk),
                    'flag_type': flag.flag,
                    'reason': flag.reason,
                    'created_at': flag.created_at.isoformat(),
                    'reviewed': flag.reviewed,
                    'comment_id': flag.comment_id,
                })
            
            # Export bans (where user is subject)
            bans = BannedUser.objects.filter(user=user).select_related('banned_by')
            bans_data = []
            
            for ban in bans:
                bans_data.append({
                    'id': str(ban.pk),
                    'reason': ban.reason,
                    'banned_until': ban.banned_until.isoformat() if ban.banned_until else None,
                    'is_active': ban.is_active,
                    'banned_by': ban.banned_by.get_username() if ban.banned_by else 'System',
                    'created_at': ban.created_at.isoformat(),
                })
            
            # Export moderation actions performed by user
            actions = ModerationAction.objects.filter(moderator=user)
            actions_data = []
            
            for action in actions:
                actions_data.append({
                    'id': str(action.pk),
                    'action': action.action,
                    'reason': action.reason,
                    'timestamp': action.timestamp.isoformat(),
                    'comment_id': action.comment_id,
                })
            
            # Export comment revisions
            revisions = CommentRevision.objects.filter(edited_by=user)
            revisions_data = []
            
            for revision in revisions:
                revisions_data.append({
                    'id': str(revision.pk),
                    'comment_id': revision.comment_id,
                    'content': revision.content,
                    'edited_at': revision.edited_at.isoformat(),
                })
            
            return {
                'export_date': timezone.now().isoformat(),
                'user': {
                    'id': user.pk,
                    'username': user.get_username(),
                    'email': user.email,
                },
                'comments': comments_data,
                'flags_created': flags_data,
                'bans_received': bans_data,
                'moderation_actions': actions_data,
                'comment_revisions': revisions_data,
                'statistics': {
                    'total_comments': len(comments_data),
                    'total_flags_created': len(flags_data),
                    'total_bans': len(bans_data),
                    'total_moderation_actions': len(actions_data),
                    'total_revisions': len(revisions_data),
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to export user data for user {user.pk}: {e}")
            raise
    
    @staticmethod
    def enforce_retention_policy() -> Dict[str, int]:
        """
        Enforce data retention policy by anonymizing old comments.
        
        Should be run periodically (e.g., via cron job or celery task).
        
        Returns:
            Dictionary with counts of anonymized items
        
        Example:
            # In management command or celery task
            >>> from django_comments.gdpr import GDPRCompliance
            >>> result = GDPRCompliance.enforce_retention_policy()
            >>> print(f"Anonymized {result['comments_anonymized']} comments")
        """
        if not comments_settings.GDPR_ENABLE_RETENTION_POLICY:
            logger.info("Retention policy is disabled")
            return {'comments_anonymized': 0}
        
        retention_days = comments_settings.GDPR_RETENTION_DAYS
        if not retention_days:
            logger.warning("Retention policy enabled but GDPR_RETENTION_DAYS not set")
            return {'comments_anonymized': 0}
        
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        # Find old comments that haven't been anonymized
        old_comments = Comment.objects.filter(
            created_at__lt=cutoff_date,
            # Only anonymize if they still have personal data
        ).exclude(
            user__isnull=True,
            user_email='',
            ip_address__isnull=True,
        )
        
        count = 0
        for comment in old_comments:
            try:
                GDPRCompliance.anonymize_comment(comment)
                count += 1
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


def enforce_retention_policy() -> Dict[str, int]:
    """Enforce data retention policy."""
    return GDPRCompliance.enforce_retention_policy()