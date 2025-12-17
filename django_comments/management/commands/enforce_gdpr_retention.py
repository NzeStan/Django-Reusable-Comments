"""
Management command to enforce GDPR data retention policy.

This command should be run periodically (e.g., daily via cron) to
automatically anonymize personal data that exceeds the retention period.

Usage:
    python manage.py enforce_gdpr_retention [--dry-run] [--verbose]
    
Examples:
    # Preview what would be anonymized
    python manage.py enforce_gdpr_retention --dry-run
    
    # Actually anonymize old data
    python manage.py enforce_gdpr_retention
    
    # Verbose output with details
    python manage.py enforce_gdpr_retention --verbose
"""

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from django.utils import timezone
from django.conf import settings as django_settings
from datetime import timedelta
from ...conf import comments_settings
from ...gdpr import GDPRCompliance
from ...utils import get_comment_model

Comment = get_comment_model()


class Command(BaseCommand):
    help = _("Enforce GDPR data retention policy by anonymizing old personal data")

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help=_('Show what would be anonymized without making changes')
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help=_('Show detailed output')
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        # FIXED: Check Django settings directly to work with @override_settings in tests
        # First try top-level settings (for tests), then fall back to DJANGO_COMMENTS_CONFIG
        comments_config = getattr(django_settings, 'DJANGO_COMMENTS_CONFIG', {})
        
        # Get GDPR_ENABLED (check both locations)
        gdpr_enabled = getattr(django_settings, 'GDPR_ENABLED', None)
        if gdpr_enabled is None:
            gdpr_enabled = comments_config.get('GDPR_ENABLED', comments_settings.GDPR_ENABLED)
        
        # Get GDPR_ENABLE_RETENTION_POLICY (check both locations)
        retention_policy_enabled = getattr(django_settings, 'GDPR_ENABLE_RETENTION_POLICY', None)
        if retention_policy_enabled is None:
            retention_policy_enabled = comments_config.get('GDPR_ENABLE_RETENTION_POLICY', 
                                                          comments_settings.GDPR_ENABLE_RETENTION_POLICY)
        
        # Get GDPR_RETENTION_DAYS (check both locations)
        retention_days = getattr(django_settings, 'GDPR_RETENTION_DAYS', None)
        if retention_days is None:
            retention_days = comments_config.get('GDPR_RETENTION_DAYS', 
                                                comments_settings.GDPR_RETENTION_DAYS)
        
        # Get GDPR_ANONYMIZE_IP_ON_RETENTION (check both locations)
        anonymize_ip = getattr(django_settings, 'GDPR_ANONYMIZE_IP_ON_RETENTION', None)
        if anonymize_ip is None:
            anonymize_ip = comments_config.get('GDPR_ANONYMIZE_IP_ON_RETENTION',
                                              comments_settings.GDPR_ANONYMIZE_IP_ON_RETENTION)
        
        # Check if GDPR features are enabled
        if not gdpr_enabled:
            self.stdout.write(self.style.WARNING(
                "GDPR compliance features are disabled. "
                "Set GDPR_ENABLED=True in settings to enable."
            ))
            return
        
        # Check if retention policy is enabled
        if not retention_policy_enabled:
            self.stdout.write(self.style.WARNING(
                "GDPR retention policy is disabled. "
                "Set GDPR_ENABLE_RETENTION_POLICY=True in settings to enable."
            ))
            return
        
        # Get retention days
        if not retention_days:
            self.stdout.write(self.style.ERROR(
                "GDPR_RETENTION_DAYS is not configured. "
                "Set this value in settings (e.g., 365 for one year)."
            ))
            return
        
        self.stdout.write(
            f"GDPR Retention Policy: {retention_days} days"
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n🔍 DRY RUN MODE - No changes will be made\n"
            ))
            
            # Calculate what would be affected
            cutoff_date = timezone.now() - timedelta(days=retention_days)
            
            # FIXED: Use <= for boundary condition
            old_comments = Comment.objects.filter(
                created_at__lte=cutoff_date
            ).exclude(
                user__isnull=True,
                user_email='',
                ip_address__isnull=True,
            )
            
            count = old_comments.count()
            
            if count == 0:
                self.stdout.write(self.style.SUCCESS(
                    "✓ No comments need anonymization"
                ))
                return
            
            self.stdout.write(
                f"DRY RUN: Would anonymize {count} comment(s) created before {cutoff_date.date()}"
            )
            
            if verbose:
                self.stdout.write(f"\nRetention days: {retention_days}")
                self.stdout.write(f"Cutoff date: {cutoff_date.date()}")
                self.stdout.write("\nSample of comments that would be anonymized:")
                for comment in old_comments[:5]:
                    self.stdout.write(
                        f"  - ID: {comment.pk}, "
                        f"Created: {comment.created_at.date()}, "
                        f"Has IP: {bool(comment.ip_address)}, "
                        f"Has Email: {bool(comment.user_email)}"
                    )
                
                if count > 5:
                    self.stdout.write(f"  ... and {count - 5} more")
            
            self.stdout.write(self.style.WARNING(
                "\nRun without --dry-run to actually anonymize this data"
            ))
            
        else:
            # Actually enforce the retention policy!
            # FIXED: Pass explicit parameters to avoid cached settings issues
            try:
                result = GDPRCompliance.enforce_retention_policy(
                    retention_policy_enabled=retention_policy_enabled,
                    retention_days=retention_days,
                    anonymize_ip=anonymize_ip
                )
                
                count = result.get('comments_anonymized', 0)
                
                if count == 0:
                    self.stdout.write(self.style.SUCCESS(
                        "✓ No comments need anonymization"
                    ))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"✓ Successfully anonymized {count} comment(s)"
                    ))
                
                if verbose:
                    self.stdout.write(f"\nRetention days: {result.get('retention_days')}")
                    self.stdout.write(f"Cutoff date: {result.get('cutoff_date')}")
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Error enforcing retention policy: {e}"
                ))
                raise