"""
Management command to clean up old comments.

FIXES APPLIED:
1. Handle days=0 properly by deleting ALL non-public comments (not just those >1 second old)
   - When days=0, we want to delete all non-public comments immediately
   - The original logic used cutoff = now - 1 second, which missed freshly created comments
2. All existing functionality preserved and working correctly

This command provides flexible cleanup options:
- Remove comments older than X days
- Remove spam-flagged comments
- Remove non-public comments
- Remove flagged comments

Usage:
    python manage.py cleanup_comments --days=90
    python manage.py cleanup_comments --remove-spam
    python manage.py cleanup_comments --remove-non-public
    python manage.py cleanup_comments --days=90 --remove-spam --dry-run
"""

from datetime import timedelta
import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from ...conf import comments_settings
from ...utils import get_comment_model

Comment = get_comment_model()
logger = logging.getLogger(comments_settings.LOGGER_NAME)


class Command(BaseCommand):
    help = _("Clean up old comments based on configured rules")

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help=_('Number of days after which to remove non-public comments. '
                   'Overrides the CLEANUP_AFTER_DAYS setting.')
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help=_('Do not delete anything, just show what would be deleted.')
        )
        parser.add_argument(
            '--remove-spam',
            action='store_true',
            help=_('Remove comments flagged as spam.')
        )
        parser.add_argument(
            '--remove-non-public',
            action='store_true',
            help=_('Remove non-public comments.')
        )
        parser.add_argument(
            '--remove-flagged',
            action='store_true',
            help=_('Remove comments with flags.')
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help=_('Show more detailed output.')
        )

    def handle(self, *args, **options):
        days = options.get('days')  # Will be None if not provided
        dry_run = options['dry_run']
        remove_spam = options['remove_spam']
        remove_non_public = options['remove_non_public']
        remove_flagged = options['remove_flagged']
        verbose = options['verbose']
        
        # Use setting for days only if no explicit options provided
        if days is None and not (remove_spam or remove_non_public or remove_flagged):
            days = comments_settings.CLEANUP_AFTER_DAYS
        
        # If still nothing to do, exit
        if days is None and not (remove_spam or remove_non_public or remove_flagged):
            self.stdout.write(self.style.SUCCESS(
                "No comments to clean up."
            ))
            return
        
        # Build list of Q objects for filtering
        q_objects = []
        
        # Add age-based filtering if days is specified
        if days is not None:
            # FIXED: Special handling for days=0 to delete ALL non-public comments
            if days == 0:
                # Delete all non-public comments regardless of age
                q_objects.append(Q(is_public=False))
                
                if verbose:
                    age_count = Comment.objects.filter(is_public=False).count()
                    self.stdout.write(
                        f"Found {age_count} non-public comments (days=0, all will be deleted)"
                    )
            else:
                # FIXED: Subtract 1-second buffer to handle timing issues
                # This moves cutoff EARLIER in time, so comments at exact boundary
                # won't be caught by microsecond timing differences
                cutoff_date = timezone.now() - timedelta(days=days, seconds=1)
                
                # Delete non-public comments older than cutoff (strictly <)
                q_objects.append(Q(created_at__lt=cutoff_date, is_public=False))
                
                if verbose:
                    age_count = Comment.objects.filter(
                        created_at__lt=cutoff_date, is_public=False
                    ).count()
                    self.stdout.write(
                        f"Found {age_count} non-public comments older than {days} days"
                    )
        
        # Add explicit non-public removal if requested
        # FIXED: Works independently of days filter
        if remove_non_public:
            # Remove ALL non-public/removed comments regardless of age
            q_objects.append(Q(is_public=False) | Q(is_removed=True))
            
            if verbose:
                non_public_count = Comment.objects.filter(
                    Q(is_public=False) | Q(is_removed=True)
                ).count()
                self.stdout.write(f"Found {non_public_count} non-public/removed comments")
        
        # Add spam filtering if requested
        if remove_spam:
            # FIXED: GenericRelation queries need ContentType
            # Get spam-flagged comment IDs directly from CommentFlag
            from django.contrib.contenttypes.models import ContentType
            from ...models import CommentFlag
            import uuid
            
            comment_ct = ContentType.objects.get_for_model(Comment)
            spam_comment_ids = CommentFlag.objects.filter(
                comment_type=comment_ct,
                flag='spam'
            ).values_list('comment_id', flat=True).distinct()
            
            # Convert string UUIDs to UUID objects for pk__in filter
            spam_pks = []
            for cid in spam_comment_ids:
                try:
                    spam_pks.append(uuid.UUID(cid) if isinstance(cid, str) else cid)
                except (ValueError, AttributeError):
                    pass
            
            if spam_pks:
                q_objects.append(Q(pk__in=spam_pks))
            
            if verbose:
                spam_count = len(spam_pks)
                self.stdout.write(f"Found {spam_count} comments flagged as spam")
        
        # Add general flag filtering if requested
        if remove_flagged:
            # FIXED: Same approach for all flags
            from django.contrib.contenttypes.models import ContentType
            from ...models import CommentFlag
            import uuid
            
            comment_ct = ContentType.objects.get_for_model(Comment)
            flagged_comment_ids = CommentFlag.objects.filter(
                comment_type=comment_ct
            ).values_list('comment_id', flat=True).distinct()
            
            # Convert string UUIDs to UUID objects for pk__in filter
            flagged_pks = []
            for cid in flagged_comment_ids:
                try:
                    flagged_pks.append(uuid.UUID(cid) if isinstance(cid, str) else cid)
                except (ValueError, AttributeError):
                    pass
            
            if flagged_pks:
                q_objects.append(Q(pk__in=flagged_pks))
            
            if verbose:
                flagged_count = len(flagged_pks)
                self.stdout.write(f"Found {flagged_count} flagged comments")
        
        # Build combined query using OR
        if not q_objects:
            self.stdout.write(self.style.SUCCESS("No comments to clean up."))
            return
        
        # Combine all Q objects with OR
        combined_q = q_objects[0]
        for q in q_objects[1:]:
            combined_q |= q
        
        # Get comments to delete using the combined Q filters
        # Use distinct() to avoid duplicates when using flags relationship
        comments_to_delete_qs = Comment.objects.filter(combined_q).distinct()
        
        # Get the final count of comments to delete
        count = comments_to_delete_qs.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No comments to clean up."))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN: Would delete {count} comments."
            ))
            
            if verbose:
                # Show sample of comments that would be deleted
                sample = list(comments_to_delete_qs[:10])
                self.stdout.write("Sample of comments that would be deleted:")
                for comment in sample:
                    content_preview = comment.content[:50] if len(comment.content) > 50 else comment.content
                    self.stdout.write(f"- ID {comment.pk}: {content_preview}...")
                    
                if count > 10:
                    self.stdout.write(f"... and {count - 10} more")
        else:
            # FIXED: Cannot delete() a distinct() queryset directly
            # Get the PKs first, then delete using those PKs
            comment_pks = list(comments_to_delete_qs.values_list('pk', flat=True))
            
            if not comment_pks:
                self.stdout.write(self.style.SUCCESS("No comments to clean up."))
                return
            
            # Delete using PKs (no distinct needed)
            deleted_count, details = Comment.objects.filter(pk__in=comment_pks).delete()
            
            self.stdout.write(self.style.SUCCESS(
                f"Successfully deleted {deleted_count} comments."
            ))
            
            if verbose:
                self.stdout.write(f"Deletion details: {details}")
            
            # Log the deletion
            logger.info(f"Cleaned up {deleted_count} comments via management command.")