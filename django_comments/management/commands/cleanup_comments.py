"""
Management command to clean up old comments.

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

from django.core.management.base import BaseCommand
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
        days = options['days'] or comments_settings.CLEANUP_AFTER_DAYS
        dry_run = options['dry_run']
        remove_spam = options['remove_spam']
        remove_non_public = options['remove_non_public']
        remove_flagged = options['remove_flagged']
        verbose = options['verbose']
        
        # If no cleanup days are configured and no explicit flags are set, 
        # there's nothing to do
        if days is None and not (remove_spam or remove_non_public or remove_flagged):
            self.stdout.write(self.style.SUCCESS(
                "No comments to clean up."
            ))
            return
        
        # Build Q objects for filtering (FIXED: avoiding queryset union issues)
        q_filters = Q(pk__in=[])  # Start with empty Q object
        
        # Add age-based filtering if days is specified
        if days is not None:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Always filter on age + non-public (preserve public comments regardless of age)
            q_filters |= Q(created_at__lt=cutoff_date, is_public=False)
            
            if verbose:
                age_count = Comment.objects.filter(
                    created_at__lt=cutoff_date, is_public=False
                ).count()
                self.stdout.write(
                    f"Found {age_count} non-public comments older than {days} days"
                )
        
        # Add explicit non-public removal if requested (and days not specified)
        if remove_non_public and days is None:
            q_filters |= Q(is_public=False) | Q(is_removed=True)
            
            if verbose:
                non_public_count = Comment.objects.filter(
                    Q(is_public=False) | Q(is_removed=True)
                ).count()
                self.stdout.write(f"Found {non_public_count} non-public comments")
        
        # Add spam filtering if requested
        if remove_spam:
            q_filters |= Q(flags__flag='spam')
            
            if verbose:
                spam_count = Comment.objects.filter(flags__flag='spam').distinct().count()
                self.stdout.write(f"Found {spam_count} comments flagged as spam")
        
        # Add general flag filtering if requested
        if remove_flagged:
            q_filters |= Q(flags__isnull=False)
            
            if verbose:
                flagged_count = Comment.objects.filter(flags__isnull=False).distinct().count()
                self.stdout.write(f"Found {flagged_count} flagged comments")
        
        # Get comments to delete using the combined Q filters
        # Use distinct() to avoid duplicates when using flags relationship
        comments_to_delete_qs = Comment.objects.filter(q_filters).distinct()
        
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
            
            # Delete using PKs (no distinct needed)
            deleted_count, details = Comment.objects.filter(pk__in=comment_pks).delete()
            
            self.stdout.write(self.style.SUCCESS(
                f"Successfully deleted {deleted_count} comments."
            ))
            
            if verbose:
                self.stdout.write(f"Deletion details: {details}")
            
            # Log the deletion
            logger.info(f"Cleaned up {deleted_count} comments via management command.")