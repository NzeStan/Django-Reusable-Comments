from datetime import timedelta
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
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
            self.stdout.write(self.style.WARNING(
                "No cleanup criteria specified. Use --days, --remove-spam, " 
                "--remove-non-public, or --remove-flagged to specify what to clean up."
            ))
            return
        
        # Build the queryset
        comments_to_delete = Comment.objects.none()
        
        # Add age-based filtering if days is specified
        if days is not None:
            cutoff_date = timezone.now() - timedelta(days=days)
            age_filter = Comment.objects.filter(created_at__lt=cutoff_date)
            
            if remove_non_public:
                # Only delete old non-public comments
                age_filter = age_filter.filter(is_public=False)
            
            comments_to_delete = comments_to_delete | age_filter
            
            if verbose:
                self.stdout.write(
                    f"Found {age_filter.count()} comments older than {days} days"
                    f"{' that are not public' if remove_non_public else ''}"
                )
        
        # Add spam filtering if requested
        if remove_spam:
            spam_comments = Comment.objects.filter(flags__flag='spam')
            comments_to_delete = comments_to_delete | spam_comments
            
            if verbose:
                self.stdout.write(f"Found {spam_comments.count()} comments flagged as spam")
        
        # Add general flag filtering if requested
        if remove_flagged:
            flagged_comments = Comment.objects.filter(flags__isnull=False).distinct()
            comments_to_delete = comments_to_delete | flagged_comments
            
            if verbose:
                self.stdout.write(f"Found {flagged_comments.count()} flagged comments")
        
        # Get the final count of comments to delete
        count = comments_to_delete.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No comments to clean up."))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN: Would delete {count} comments."
            ))
            
            if verbose:
                # Show sample of comments that would be deleted
                sample = comments_to_delete[:10]
                self.stdout.write("Sample of comments that would be deleted:")
                for comment in sample:
                    self.stdout.write(f"- ID {comment.pk}: {comment.content[:50]}...")
                    
                if count > 10:
                    self.stdout.write(f"... and {count - 10} more")
        else:
            # Actually delete the comments
            deleted_count, details = comments_to_delete.delete()
            
            self.stdout.write(self.style.SUCCESS(
                f"Successfully deleted {deleted_count} comments."
            ))
            
            # Log the deletion
            logger.info(f"Cleaned up {deleted_count} comments via management command.")