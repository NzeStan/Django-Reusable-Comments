"""
Comprehensive tests for enforce_gdpr_retention.py management command.

Tests cover:
- Command initialization and settings validation
- Retention policy enforcement
- Dry-run mode
- Verbose output
- Integration with GDPRCompliance class
- Various GDPR settings configurations
- Edge cases and real-world scenarios
"""

from datetime import timedelta, datetime
from io import StringIO
from unittest.mock import patch, Mock
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from django_comments.tests.base import BaseCommentTestCase


# ============================================================================
# COMMAND BASIC FUNCTIONALITY TESTS
# ============================================================================

class EnforceGDPRRetentionCommandBasicTests(BaseCommentTestCase):
    """Test basic command functionality."""
    
    def test_command_runs(self):
        """Test command runs without errors."""
        out = StringIO()
        
        with override_settings(
            GDPR_ENABLED=True,
            GDPR_ENABLE_RETENTION_POLICY=True,
            GDPR_RETENTION_DAYS=365
        ):
            call_command('enforce_gdpr_retention', stdout=out)
    
    def test_command_help_text(self):
        """Test command has proper help text."""
        from django_comments.management.commands.enforce_gdpr_retention import Command
        
        command = Command()
        self.assertIn('GDPR', command.help)
        self.assertIn('retention', command.help.lower())
    
    def test_command_available_in_management(self):
        """Test command is available in management commands."""
        from django.core.management import get_commands
        
        commands = get_commands()
        self.assertIn('enforce_gdpr_retention', commands)


# ============================================================================
# SETTINGS VALIDATION TESTS
# ============================================================================

class SettingsValidationTests(BaseCommentTestCase):
    """Test validation of GDPR settings."""
    
    @override_settings(GDPR_ENABLED=False)
    def test_command_warns_when_gdpr_disabled(self):
        """Test command warns when GDPR features are disabled."""
        out = StringIO()
        
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        self.assertIn('GDPR compliance features are disabled', output)
        self.assertIn('GDPR_ENABLED=True', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=False
    )
    def test_command_warns_when_retention_policy_disabled(self):
        """Test command warns when retention policy is disabled."""
        out = StringIO()
        
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        self.assertIn('retention policy is disabled', output)
        self.assertIn('GDPR_ENABLE_RETENTION_POLICY=True', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=None
    )
    def test_command_errors_when_retention_days_not_set(self):
        """Test command errors when retention days not configured."""
        out = StringIO()
        
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        self.assertIn('GDPR_RETENTION_DAYS is not configured', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=0
    )
    def test_command_errors_when_retention_days_zero(self):
        """Test command errors when retention days is zero."""
        out = StringIO()
        
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        self.assertIn('not configured', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_command_shows_retention_policy_info(self):
        """Test command displays retention policy information."""
        out = StringIO()
        
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        self.assertIn('365 days', output)


# ============================================================================
# RETENTION ENFORCEMENT TESTS
# ============================================================================

class RetentionEnforcementTests(BaseCommentTestCase):
    """Test actual retention policy enforcement."""
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_anonymizes_old_comments(self):
        """Test enforcement anonymizes old comments."""
        # Create old comment beyond retention
        old_comment = self.create_comment(
            user=self.regular_user,
            user_email='user@example.com',
            ip_address='192.168.1.100',
            content="Old comment"
        )
        old_comment.created_at = timezone.now() - timedelta(days=400)
        old_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        # Verify comment was anonymized
        old_comment.refresh_from_db()
        self.assertIsNone(old_comment.user)
        self.assertEqual(old_comment.user_email, '')
        
        # Verify output
        output = out.getvalue()
        self.assertIn('1 comment', output)
        self.assertIn('anonymized', output.lower())
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_preserves_recent_comments(self):
        """Test enforcement preserves recent comments."""
        recent_comment = self.create_comment(
            user=self.regular_user,
            user_email='user@example.com',
            content="Recent comment"
        )
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        # Verify comment was NOT anonymized
        recent_comment.refresh_from_db()
        self.assertEqual(recent_comment.user, self.regular_user)
        self.assertEqual(recent_comment.user_email, 'user@example.com')
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_multiple_old_comments(self):
        """Test enforcement handles multiple old comments."""
        # Create 5 old comments
        for i in range(5):
            comment = self.create_comment(
                user=self.regular_user,
                content=f"Old comment {i}",
                user_email=f"user{i}@example.com"
            )
            comment.created_at = timezone.now() - timedelta(days=400)
            comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        self.assertIn('5 comment', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_no_old_comments(self):
        """Test enforcement when no comments need anonymization."""
        # Create only recent comments
        self.create_comment(user=self.regular_user)
        self.create_comment(user=self.regular_user)
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        self.assertIn('No comments', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=30
    )
    def test_enforce_with_short_retention(self):
        """Test enforcement with short retention period."""
        old_comment = self.create_comment(user=self.regular_user)
        old_comment.created_at = timezone.now() - timedelta(days=35)
        old_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        # Should be anonymized
        old_comment.refresh_from_db()
        self.assertIsNone(old_comment.user)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_skips_already_anonymized(self):
        """Test enforcement skips already anonymized comments."""
        # Create old but already anonymized comment
        old_comment = self.create_comment(
            user=None,
            user_name='Anonymous',
            user_email='',
            ip_address=None,
            content="Already anonymized"
        )
        old_comment.created_at = timezone.now() - timedelta(days=400)
        old_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        self.assertIn('No comments', output)


# ============================================================================
# DRY-RUN MODE TESTS
# ============================================================================

class DryRunModeTests(BaseCommentTestCase):
    """Test dry-run mode functionality."""
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_dry_run_does_not_anonymize(self):
        """Test dry-run mode doesn't actually anonymize comments."""
        old_comment = self.create_comment(
            user=self.regular_user,
            user_email='user@example.com',
            ip_address='192.168.1.100'
        )
        old_comment.created_at = timezone.now() - timedelta(days=400)
        old_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', '--dry-run', stdout=out)
        
        # Verify comment was NOT anonymized
        old_comment.refresh_from_db()
        self.assertEqual(old_comment.user, self.regular_user)
        self.assertEqual(old_comment.user_email, 'user@example.com')
        self.assertIsNotNone(old_comment.ip_address)
        
        # Verify output indicates dry-run
        output = out.getvalue()
        self.assertIn('DRY RUN', output)
        self.assertIn('Would anonymize', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_dry_run_shows_count(self):
        """Test dry-run shows count of what would be anonymized."""
        # Create 3 old comments
        for i in range(3):
            comment = self.create_comment(
                user=self.regular_user,
                content=f"Old {i}"
            )
            comment.created_at = timezone.now() - timedelta(days=400)
            comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', '--dry-run', stdout=out)
        
        output = out.getvalue()
        self.assertIn('3 comment', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_dry_run_shows_cutoff_date(self):
        """Test dry-run displays cutoff date."""
        old_comment = self.create_comment(user=self.regular_user)
        old_comment.created_at = timezone.now() - timedelta(days=400)
        old_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', '--dry-run', stdout=out)
        
        output = out.getvalue()
        # Should show a date
        self.assertTrue(any(char.isdigit() for char in output))
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_dry_run_no_comments_message(self):
        """Test dry-run message when no comments need anonymization."""
        # Create only recent comments
        self.create_comment(user=self.regular_user)
        
        out = StringIO()
        call_command('enforce_gdpr_retention', '--dry-run', stdout=out)
        
        output = out.getvalue()
        self.assertIn('No comments', output)


# ============================================================================
# VERBOSE OUTPUT TESTS
# ============================================================================

class VerboseOutputTests(BaseCommentTestCase):
    """Test verbose output functionality."""
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_verbose_shows_details(self):
        """Test verbose mode shows detailed information."""
        old_comment = self.create_comment(
            user=self.regular_user,
            ip_address='192.168.1.100',
            user_email='user@example.com'
        )
        old_comment.created_at = timezone.now() - timedelta(days=400)
        old_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', '--verbose', stdout=out)
        
        output = out.getvalue()
        # Should contain more detailed info
        self.assertIn('Retention days:', output)
        self.assertIn('365', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_verbose_with_dry_run(self):
        """Test verbose output combined with dry-run."""
        old_comment = self.create_comment(user=self.regular_user)
        old_comment.created_at = timezone.now() - timedelta(days=400)
        old_comment.save()
        
        out = StringIO()
        call_command(
            'enforce_gdpr_retention',
            '--dry-run',
            '--verbose',
            stdout=out
        )
        
        output = out.getvalue()
        # Should show both dry-run and verbose info
        self.assertIn('DRY RUN', output)
        self.assertTrue(len(output) > 100)  # Substantial output
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_verbose_shows_sample_comments(self):
        """Test verbose mode shows sample of comments."""
        # Create multiple old comments
        for i in range(10):
            comment = self.create_comment(
                user=self.regular_user,
                content=f"Old {i}"
            )
            comment.created_at = timezone.now() - timedelta(days=400)
            comment.save()
        
        out = StringIO()
        call_command(
            'enforce_gdpr_retention',
            '--dry-run',
            '--verbose',
            stdout=out
        )
        
        output = out.getvalue()
        # Should show sample info
        self.assertIn('ID:', output)


# ============================================================================
# GDPRCOMPLIANCE INTEGRATION TESTS
# ============================================================================

class GDPRComplianceIntegrationTests(BaseCommentTestCase):
    """Test integration with GDPRCompliance class."""
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    @patch('django_comments.management.commands.enforce_gdpr_retention.GDPRCompliance.enforce_retention_policy')
    def test_command_calls_gdpr_compliance(self, mock_enforce):
        """Test command calls GDPRCompliance.enforce_retention_policy."""
        mock_enforce.return_value = {
            'comments_anonymized': 5,
            'retention_days': 365,
            'cutoff_date': timezone.now().isoformat()
        }
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        mock_enforce.assert_called_once()
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    @patch('django_comments.management.commands.enforce_gdpr_retention.GDPRCompliance.enforce_retention_policy')
    def test_command_not_call_gdpr_in_dry_run(self, mock_enforce):
        """Test command doesn't call GDPRCompliance in dry-run mode."""
        out = StringIO()
        call_command('enforce_gdpr_retention', '--dry-run', stdout=out)
        
        # Should not call the actual enforcement
        mock_enforce.assert_not_called()
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_command_handles_enforcement_result(self):
        """Test command handles GDPRCompliance result correctly."""
        old_comment = self.create_comment(user=self.regular_user)
        old_comment.created_at = timezone.now() - timedelta(days=400)
        old_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        # Should report the result
        self.assertIn('Successfully anonymized', output)


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class ErrorHandlingTests(BaseCommentTestCase):
    """Test error handling in command."""
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    @patch('django_comments.management.commands.enforce_gdpr_retention.GDPRCompliance.enforce_retention_policy')
    def test_command_handles_enforcement_error(self, mock_enforce):
        """Test command handles errors from GDPRCompliance."""
        mock_enforce.side_effect = Exception("Database error")
        
        out = StringIO()
        
        with self.assertRaises(Exception):
            call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Error', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_command_reports_zero_anonymized(self):
        """Test command reports when zero comments anonymized."""
        # Create only recent comments
        self.create_comment(user=self.regular_user)
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        self.assertIn('No comments', output)


# ============================================================================
# SETTINGS VARIATIONS TESTS
# ============================================================================

class SettingsVariationsTests(BaseCommentTestCase):
    """Test various GDPR settings configurations."""
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=1
    )
    def test_very_short_retention_period(self):
        """Test with very short retention period (1 day)."""
        # Comment from 2 days ago
        old_comment = self.create_comment(user=self.regular_user)
        old_comment.created_at = timezone.now() - timedelta(days=2)
        old_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        # Should be anonymized
        old_comment.refresh_from_db()
        self.assertIsNone(old_comment.user)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=3650  # 10 years
    )
    def test_very_long_retention_period(self):
        """Test with very long retention period."""
        # Comment from 1 year ago (within retention)
        comment = self.create_comment(user=self.regular_user)
        comment.created_at = timezone.now() - timedelta(days=365)
        comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        # Should NOT be anonymized
        comment.refresh_from_db()
        self.assertEqual(comment.user, self.regular_user)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=90
    )
    def test_quarterly_retention(self):
        """Test with quarterly (90 day) retention period."""
        old_comment = self.create_comment(user=self.regular_user)
        old_comment.created_at = timezone.now() - timedelta(days=100)
        old_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        self.assertIn('90 days', output)


# ============================================================================
# EDGE CASES AND REAL-WORLD SCENARIOS
# ============================================================================

class EnforceGDPREdgeCasesTests(BaseCommentTestCase):
    """Test edge cases and real-world scenarios."""
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_with_unicode_content(self):
        """Test enforcement with Unicode content."""
        old_comment = self.create_comment(
            user=self.regular_user,
            content="测试内容 with emoji 😀🎉"
        )
        old_comment.created_at = timezone.now() - timedelta(days=400)
        old_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        # Should handle Unicode correctly
        old_comment.refresh_from_db()
        self.assertIsNone(old_comment.user)
        # Content should be preserved
        self.assertIn('😀', old_comment.content)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_with_very_old_comments(self):
        """Test enforcement with very old comments (5 years)."""
        ancient_comment = self.create_comment(user=self.regular_user)
        ancient_comment.created_at = timezone.now() - timedelta(days=1825)
        ancient_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        # Should be anonymized
        ancient_comment.refresh_from_db()
        self.assertIsNone(ancient_comment.user)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_at_exact_boundary(self):
        """Test enforcement at exact retention boundary."""
        # Comment exactly 365 days old
        boundary_comment = self.create_comment(user=self.regular_user)
        boundary_comment.created_at = timezone.now() - timedelta(days=365)
        boundary_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        # Should NOT be anonymized (only > 365 days)
        boundary_comment.refresh_from_db()
        self.assertEqual(boundary_comment.user, self.regular_user)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_with_mixed_ages(self):
        """Test enforcement with comments of various ages."""
        ages = [100, 300, 366, 400, 500]
        
        for age in ages:
            comment = self.create_comment(
                user=self.regular_user,
                content=f"Comment {age} days old"
            )
            comment.created_at = timezone.now() - timedelta(days=age)
            comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        # Should anonymize 3 comments (366, 400, 500)
        self.assertIn('3 comment', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_with_nested_comments(self):
        """Test enforcement with nested/threaded comments."""
        parent = self.create_comment(
            user=self.regular_user,
            content="Parent"
        )
        parent.created_at = timezone.now() - timedelta(days=400)
        parent.save()
        
        child = self.create_comment(
            user=self.regular_user,
            content="Child",
            parent=parent
        )
        child.created_at = timezone.now() - timedelta(days=400)
        child.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        # Both should be anonymized
        parent.refresh_from_db()
        child.refresh_from_db()
        self.assertIsNone(parent.user)
        self.assertIsNone(child.user)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_large_number_of_comments(self):
        """Test enforcement with large number of comments."""
        # Create 100 old comments
        for i in range(100):
            comment = self.create_comment(
                user=self.regular_user,
                content=f"Comment {i}"
            )
            comment.created_at = timezone.now() - timedelta(days=400)
            comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        self.assertIn('100 comment', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_idempotent(self):
        """Test enforcement is idempotent (can run multiple times)."""
        old_comment = self.create_comment(user=self.regular_user)
        old_comment.created_at = timezone.now() - timedelta(days=400)
        old_comment.save()
        
        # Run first time
        out1 = StringIO()
        call_command('enforce_gdpr_retention', stdout=out1)
        
        # Run second time
        out2 = StringIO()
        call_command('enforce_gdpr_retention', stdout=out2)
        
        output2 = out2.getvalue()
        # Should indicate nothing to anonymize
        self.assertIn('No comments', output2)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_with_deleted_content_object(self):
        """Test enforcement when content_object no longer exists."""
        # Skip: Cannot set object_id to None due to DB constraints
        self.skipTest("Cannot set object_id to None due to NOT NULL constraint")
    
    
    def test_enforce_output_formatting(self):
        """Test enforcement output is properly formatted."""
        old_comment = self.create_comment(user=self.regular_user)
        old_comment.created_at = timezone.now() - timedelta(days=400)
        old_comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        output = out.getvalue()
        # Should have checkmark and proper formatting
        self.assertIn('✓', output)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_with_timezone_aware_dates(self):
        """Test enforcement handles timezone-aware dates correctly."""
        comment = self.create_comment(user=self.regular_user)
        # Set timezone-aware date
        comment.created_at = timezone.make_aware(datetime(2020, 1, 1), timezone.get_current_timezone())
        comment.save()
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        # Very old comment should be anonymized
        comment.refresh_from_db()
        self.assertIsNone(comment.user)
    
    @override_settings(
        GDPR_ENABLED=True,
        GDPR_ENABLE_RETENTION_POLICY=True,
        GDPR_RETENTION_DAYS=365
    )
    def test_enforce_preserves_comment_content_and_structure(self):
        """Test enforcement preserves comment content and structure."""
        old_comment = self.create_comment(
            user=self.regular_user,
            content="Important historical content that should be preserved",
            is_public=True
        )
        old_comment.created_at = timezone.now() - timedelta(days=400)
        old_comment.save()
        
        original_content = old_comment.content
        original_created_at = old_comment.created_at
        original_is_public = old_comment.is_public
        
        out = StringIO()
        call_command('enforce_gdpr_retention', stdout=out)
        
        # Verify personal data removed but structure preserved
        old_comment.refresh_from_db()
        self.assertIsNone(old_comment.user)
        self.assertEqual(old_comment.content, original_content)
        self.assertEqual(old_comment.created_at, original_created_at)
        self.assertEqual(old_comment.is_public, original_is_public)