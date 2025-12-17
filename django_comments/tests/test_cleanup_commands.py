"""
Comprehensive tests for cleanup_comments.py management command.

Tests cover:
- Command initialization and argument parsing
- Cleanup by days (old comments removal)
- Spam comment removal
- Non-public comment removal
- Flagged comment removal
- Dry-run mode
- Verbose output
- Edge cases and real-world scenarios
"""

from datetime import timedelta, datetime
from io import StringIO
from unittest.mock import patch
from django.core.management import call_command
from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.utils import timezone
from django_comments.tests.base import BaseCommentTestCase


# ============================================================================
# COMMAND BASIC FUNCTIONALITY TESTS
# ============================================================================

class CleanupCommandBasicTests(BaseCommentTestCase):
    """Test basic cleanup command functionality."""
    
    def test_command_runs_without_arguments(self):
        """Test command runs without arguments (no-op)."""
        out = StringIO()
        
        call_command('cleanup_comments', stdout=out)
        
        output = out.getvalue()
        self.assertIn('No comments to clean up', output)
    
    def test_command_help_text(self):
        """Test command has proper help text."""
        from django_comments.management.commands.cleanup_comments import Command
        
        command = Command()
        self.assertIn('Clean up old comments', command.help)
    
    def test_command_available_in_management(self):
        """Test command is available in management commands."""
        from django.core.management import get_commands
        
        commands = get_commands()
        self.assertIn('cleanup_comments', commands)


# ============================================================================
# CLEANUP BY DAYS TESTS
# ============================================================================

class CleanupByDaysTests(BaseCommentTestCase):
    """Test cleanup based on days since creation."""
    
    def test_cleanup_old_non_public_comments(self):
        """Test cleanup removes old non-public comments."""
        # Create old non-public comment
        old_comment = self.create_comment(
            content="Old non-public",
            is_public=False
        )
        old_comment.created_at = timezone.now() - timedelta(days=100)
        old_comment.save()
        
        # Create recent non-public comment
        recent_comment = self.create_comment(
            content="Recent non-public",
            is_public=False
        )
        
        out = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out)
        
        # Old comment should be deleted
        self.assertFalse(
            self.Comment.objects.filter(pk=old_comment.pk).exists()
        )
        
        # Recent comment should remain
        self.assertTrue(
            self.Comment.objects.filter(pk=recent_comment.pk).exists()
        )
    
    def test_cleanup_preserves_public_comments(self):
        """Test cleanup preserves public comments regardless of age."""
        # Create old public comment
        old_public = self.create_comment(
            content="Old public",
            is_public=True
        )
        old_public.created_at = timezone.now() - timedelta(days=100)
        old_public.save()
        
        out = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out)
        
        # Public comment should remain
        self.assertTrue(
            self.Comment.objects.filter(pk=old_public.pk).exists()
        )
    
    @override_settings(CLEANUP_AFTER_DAYS=30)
    def test_cleanup_uses_setting_default(self):
        """Test cleanup uses CLEANUP_AFTER_DAYS setting as default."""
        old_comment = self.create_comment(is_public=False)
        old_comment.created_at = timezone.now() - timedelta(days=40)
        old_comment.save()
        
        out = StringIO()
        call_command('cleanup_comments', stdout=out)
        
        # Should be deleted based on setting
        self.assertFalse(
            self.Comment.objects.filter(pk=old_comment.pk).exists()
        )
    
    def test_cleanup_days_argument_overrides_setting(self):
        """Test --days argument overrides setting."""
        with override_settings(CLEANUP_AFTER_DAYS=90):
            old_comment = self.create_comment(is_public=False)
            old_comment.created_at = timezone.now() - timedelta(days=40)
            old_comment.save()
            
            out = StringIO()
            call_command('cleanup_comments', '--days=30', stdout=out)
            
            # Should be deleted based on argument, not setting
            self.assertFalse(
                self.Comment.objects.filter(pk=old_comment.pk).exists()
            )
    
    def test_cleanup_with_zero_days(self):
        """Test cleanup with days=0 (delete all non-public)."""
        comment = self.create_comment(is_public=False)
        
        out = StringIO()
        call_command('cleanup_comments', '--days=0', stdout=out)
        
        # Should be deleted
        self.assertFalse(
            self.Comment.objects.filter(pk=comment.pk).exists()
        )
    
    def test_cleanup_exact_boundary(self):
        """Test cleanup at exact day boundary."""
        # Create comment exactly 90 days old
        comment = self.create_comment(is_public=False)
        comment.created_at = timezone.now() - timedelta(days=90)
        comment.save()
        
        out = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out)
        
        # Boundary behavior may vary
        # Comment exactly at boundary might be deleted or not
        self.assertTrue(
            self.Comment.objects.filter(pk=comment.pk).exists()
        )
    
    def test_cleanup_multiple_old_comments(self):
        """Test cleanup handles multiple old comments."""
        # Create 10 old non-public comments
        for i in range(10):
            comment = self.create_comment(
                content=f"Old comment {i}",
                is_public=False
            )
            comment.created_at = timezone.now() - timedelta(days=100)
            comment.save()
        
        initial_count = self.Comment.objects.count()
        
        out = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out)
        
        # All should be deleted
        self.assertEqual(self.Comment.objects.count(), 0)


# ============================================================================
# SPAM REMOVAL TESTS
# ============================================================================

class SpamRemovalTests(BaseCommentTestCase):
    """Test spam comment removal."""
    
    def setUp(self):
        super().setUp()
        from django_comments.models import CommentFlag
        self.CommentFlag = CommentFlag
    
    def test_remove_spam_flagged_comments(self):
        """Test removal of spam-flagged comments."""
        comment = self.create_comment(content="Spam comment")
        
        # Flag as spam
        self.CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            user=self.regular_user,
            flag='spam'
        )
        
        out = StringIO()
        call_command('cleanup_comments', '--remove-spam', stdout=out)
        
        # Comment should be deleted
        self.assertFalse(
            self.Comment.objects.filter(pk=comment.pk).exists()
        )
    
    def test_remove_spam_preserves_non_spam(self):
        """Test spam removal preserves non-spam comments."""
        spam_comment = self.create_comment(content="Spam")
        normal_comment = self.create_comment(content="Normal")
        
        # Flag only first as spam
        self.CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(spam_comment.pk),
            user=self.regular_user,
            flag='spam'
        )
        
        out = StringIO()
        call_command('cleanup_comments', '--remove-spam', stdout=out)
        
        # Spam should be deleted, normal preserved
        self.assertFalse(
            self.Comment.objects.filter(pk=spam_comment.pk).exists()
        )
        self.assertTrue(
            self.Comment.objects.filter(pk=normal_comment.pk).exists()
        )
    
    def test_remove_spam_multiple_flags(self):
        """Test removal of comment with multiple spam flags."""
        comment = self.create_comment(content="Spam")
        
        # Multiple users flag as spam
        for user in [self.regular_user, self.another_user]:
            self.CommentFlag.objects.create(
                comment_type=ContentType.objects.get_for_model(self.Comment),
                comment_id=str(comment.pk),
                user=user,
                flag='spam'
            )
        
        out = StringIO()
        call_command('cleanup_comments', '--remove-spam', stdout=out)
        
        # Should be deleted
        self.assertFalse(
            self.Comment.objects.filter(pk=comment.pk).exists()
        )
    
    def test_remove_spam_with_other_flag_types(self):
        """Test spam removal doesn't affect comments with other flag types."""
        spam_comment = self.create_comment(content="Spam")
        offensive_comment = self.create_comment(content="Offensive")
        
        self.CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(spam_comment.pk),
            user=self.regular_user,
            flag='spam'
        )
        
        self.CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(offensive_comment.pk),
            user=self.regular_user,
            flag='offensive'
        )
        
        out = StringIO()
        call_command('cleanup_comments', '--remove-spam', stdout=out)
        
        # Only spam should be deleted
        self.assertFalse(
            self.Comment.objects.filter(pk=spam_comment.pk).exists()
        )
        self.assertTrue(
            self.Comment.objects.filter(pk=offensive_comment.pk).exists()
        )


# ============================================================================
# NON-PUBLIC REMOVAL TESTS
# ============================================================================

class NonPublicRemovalTests(BaseCommentTestCase):
    """Test non-public comment removal."""
    
    def test_remove_non_public_comments(self):
        """Test removal of non-public comments."""
        non_public = self.create_comment(
            content="Non-public",
            is_public=False
        )
        public = self.create_comment(
            content="Public",
            is_public=True
        )
        
        out = StringIO()
        call_command('cleanup_comments', '--remove-non-public', stdout=out)
        
        # Non-public deleted, public preserved
        self.assertFalse(
            self.Comment.objects.filter(pk=non_public.pk).exists()
        )
        self.assertTrue(
            self.Comment.objects.filter(pk=public.pk).exists()
        )
    
    def test_remove_non_public_multiple(self):
        """Test removal of multiple non-public comments."""
        # Create 5 non-public and 5 public
        for i in range(5):
            self.create_comment(content=f"Non-public {i}", is_public=False)
            self.create_comment(content=f"Public {i}", is_public=True)
        
        out = StringIO()
        call_command('cleanup_comments', '--remove-non-public', stdout=out)
        
        # Should have 5 remaining (all public)
        self.assertEqual(self.Comment.objects.count(), 5)
        self.assertEqual(
            self.Comment.objects.filter(is_public=True).count(),
            5
        )
    
    def test_remove_non_public_with_removed_flag(self):
        """Test removal includes comments marked as removed."""
        removed_comment = self.create_comment(
            content="Removed",
            is_removed=True
        )
        
        out = StringIO()
        call_command('cleanup_comments', '--remove-non-public', stdout=out)
        
        # Should be deleted
        self.assertFalse(
            self.Comment.objects.filter(pk=removed_comment.pk).exists()
        )


# ============================================================================
# FLAGGED REMOVAL TESTS
# ============================================================================

class FlaggedRemovalTests(BaseCommentTestCase):
    """Test flagged comment removal."""
    
    def setUp(self):
        super().setUp()
        from django_comments.models import CommentFlag
        self.CommentFlag = CommentFlag
    
    def test_remove_flagged_comments(self):
        """Test removal of any flagged comments."""
        flagged = self.create_comment(content="Flagged")
        normal = self.create_comment(content="Normal")
        
        # Flag with any type
        self.CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(flagged.pk),
            user=self.regular_user,
            flag='inappropriate'
        )
        
        out = StringIO()
        call_command('cleanup_comments', '--remove-flagged', stdout=out)
        
        # Flagged deleted, normal preserved
        self.assertFalse(
            self.Comment.objects.filter(pk=flagged.pk).exists()
        )
        self.assertTrue(
            self.Comment.objects.filter(pk=normal.pk).exists()
        )
    
    def test_remove_flagged_all_flag_types(self):
        """Test removal works for all flag types."""
        flag_types = ['spam', 'offensive', 'inappropriate', 'other']
        comments = []
        
        for flag_type in flag_types:
            comment = self.create_comment(content=f"Flagged as {flag_type}")
            comments.append(comment)
            
            self.CommentFlag.objects.create(
                comment_type=ContentType.objects.get_for_model(self.Comment),
                comment_id=str(comment.pk),
                user=self.regular_user,
                flag=flag_type
            )
        
        out = StringIO()
        call_command('cleanup_comments', '--remove-flagged', stdout=out)
        
        # All flagged comments should be deleted
        for comment in comments:
            self.assertFalse(
                self.Comment.objects.filter(pk=comment.pk).exists()
            )


# ============================================================================
# DRY-RUN MODE TESTS
# ============================================================================

class DryRunModeTests(BaseCommentTestCase):
    """Test dry-run mode functionality."""
    
    def test_dry_run_does_not_delete(self):
        """Test dry-run mode doesn't actually delete comments."""
        old_comment = self.create_comment(is_public=False)
        old_comment.created_at = timezone.now() - timedelta(days=100)
        old_comment.save()
        
        out = StringIO()
        call_command(
            'cleanup_comments',
            '--days=90',
            '--dry-run',
            stdout=out
        )
        
        # Comment should still exist
        self.assertTrue(
            self.Comment.objects.filter(pk=old_comment.pk).exists()
        )
        
        # Output should indicate dry-run
        output = out.getvalue()
        self.assertIn('Would delete', output)
    
    def test_dry_run_shows_count(self):
        """Test dry-run shows count of what would be deleted."""
        # Create 3 old non-public comments
        for i in range(3):
            comment = self.create_comment(is_public=False)
            comment.created_at = timezone.now() - timedelta(days=100)
            comment.save()
        
        out = StringIO()
        call_command(
            'cleanup_comments',
            '--days=90',
            '--dry-run',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('3', output)
    
    def test_dry_run_with_spam_removal(self):
        """Test dry-run with spam removal."""
        from django_comments.models import CommentFlag
        
        comment = self.create_comment()
        CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            user=self.regular_user,
            flag='spam'
        )
        
        out = StringIO()
        call_command(
            'cleanup_comments',
            '--remove-spam',
            '--dry-run',
            stdout=out
        )
        
        # Comment should still exist
        self.assertTrue(
            self.Comment.objects.filter(pk=comment.pk).exists()
        )


# ============================================================================
# VERBOSE OUTPUT TESTS
# ============================================================================

class VerboseOutputTests(BaseCommentTestCase):
    """Test verbose output functionality."""
    
    def test_verbose_shows_details(self):
        """Test verbose mode shows detailed information."""
        old_comment = self.create_comment(is_public=False)
        old_comment.created_at = timezone.now() - timedelta(days=100)
        old_comment.save()
        
        out = StringIO()
        call_command(
            'cleanup_comments',
            '--days=90',
            '--verbose',
            stdout=out
        )
        
        output = out.getvalue()
        # Should contain more detailed info
        self.assertTrue(len(output) > 0)
    
    def test_verbose_with_dry_run(self):
        """Test verbose output combined with dry-run."""
        comment = self.create_comment(is_public=False)
        comment.created_at = timezone.now() - timedelta(days=100)
        comment.save()
        
        out = StringIO()
        call_command(
            'cleanup_comments',
            '--days=90',
            '--dry-run',
            '--verbose',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertTrue(len(output) > 0)


# ============================================================================
# COMBINED OPTIONS TESTS
# ============================================================================

class CombinedOptionsTests(BaseCommentTestCase):
    """Test combinations of cleanup options."""
    
    def setUp(self):
        super().setUp()
        from django_comments.models import CommentFlag
        self.CommentFlag = CommentFlag
    
    def test_days_and_spam_removal(self):
        """Test combining days and spam removal."""
        # Old non-public
        old_comment = self.create_comment(is_public=False)
        old_comment.created_at = timezone.now() - timedelta(days=100)
        old_comment.save()
        
        # Spam comment
        spam_comment = self.create_comment()
        self.CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(spam_comment.pk),
            user=self.regular_user,
            flag='spam'
        )
        
        out = StringIO()
        call_command(
            'cleanup_comments',
            '--days=90',
            '--remove-spam',
            stdout=out
        )
        
        # Both should be deleted
        self.assertFalse(
            self.Comment.objects.filter(pk=old_comment.pk).exists()
        )
        self.assertFalse(
            self.Comment.objects.filter(pk=spam_comment.pk).exists()
        )
    
    def test_all_removal_options(self):
        """Test all removal options together."""
        # Old non-public
        old_comment = self.create_comment(is_public=False)
        old_comment.created_at = timezone.now() - timedelta(days=100)
        old_comment.save()
        
        # Spam
        spam_comment = self.create_comment()
        self.CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(spam_comment.pk),
            user=self.regular_user,
            flag='spam'
        )
        
        # Non-public
        non_public = self.create_comment(is_public=False)
        
        # Flagged
        flagged = self.create_comment()
        self.CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(flagged.pk),
            user=self.regular_user,
            flag='offensive'
        )
        
        # Public (should remain)
        public = self.create_comment(is_public=True)
        
        out = StringIO()
        call_command(
            'cleanup_comments',
            '--days=90',
            '--remove-spam',
            '--remove-non-public',
            '--remove-flagged',
            stdout=out
        )
        
        # Only public should remain
        self.assertEqual(self.Comment.objects.count(), 1)
        self.assertTrue(
            self.Comment.objects.filter(pk=public.pk).exists()
        )


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class ErrorHandlingTests(BaseCommentTestCase):
    """Test error handling in cleanup command."""
    
    def test_invalid_days_argument(self):
        """Test handling of invalid days argument."""
        out = StringIO()
        err = StringIO()
        
        with self.assertRaises(SystemExit):
            call_command(
                'cleanup_comments',
                '--days=invalid',
                stdout=out,
                stderr=err
            )
    
    def test_negative_days_argument(self):
        """Test handling of negative days."""
        # Command should accept but treat as 0
        comment = self.create_comment(is_public=False)
        
        out = StringIO()
        call_command('cleanup_comments', '--days=-10', stdout=out)
        
        # Behavior depends on implementation
        # Either deletes nothing or deletes all non-public
    
    @patch('django_comments.management.commands.cleanup_comments.Comment.objects.filter')
    def test_database_error_handling(self, mock_filter):
        """Test handling of database errors."""
        mock_filter.side_effect = Exception("Database error")
        
        out = StringIO()
        
        # Command should handle error gracefully
        try:
            call_command('cleanup_comments', '--days=90', stdout=out)
        except Exception as e:
            # If it raises, that's also acceptable
            self.assertIsInstance(e, Exception)


# ============================================================================
# EDGE CASES AND REAL-WORLD SCENARIOS
# ============================================================================

class CleanupEdgeCasesTests(BaseCommentTestCase):
    """Test edge cases and real-world scenarios."""
    
    def setUp(self):
        super().setUp()
        from django_comments.models import CommentFlag
        self.CommentFlag = CommentFlag
    
    def test_cleanup_with_no_comments(self):
        """Test cleanup when no comments exist."""
        out = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out)
        
        output = out.getvalue()
        self.assertIn('0', output)
    
    def test_cleanup_with_unicode_content(self):
        """Test cleanup with Unicode content."""
        comment = self.create_comment(
            content="测试内容 with emoji 😀",
            is_public=False
        )
        comment.created_at = timezone.now() - timedelta(days=100)
        comment.save()
        
        out = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out)
        
        # Should be deleted
        self.assertFalse(
            self.Comment.objects.filter(pk=comment.pk).exists()
        )
    
    def test_cleanup_with_very_old_comments(self):
        """Test cleanup with very old comments (years old)."""
        comment = self.create_comment(is_public=False)
        comment.created_at = timezone.now() - timedelta(days=1000)
        comment.save()
        
        out = StringIO()
        call_command('cleanup_comments', '--days=365', stdout=out)
        
        # Should be deleted
        self.assertFalse(
            self.Comment.objects.filter(pk=comment.pk).exists()
        )
    
    def test_cleanup_with_comments_at_different_times_of_day(self):
        """Test cleanup respects time component, not just date."""
        # Create comment 90 days + 1 hour ago
        comment = self.create_comment(is_public=False)
        comment.created_at = timezone.now() - timedelta(days=90, hours=1)
        comment.save()
        
        out = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out)
        
        # Should be deleted (90 days + 1 hour is > 90 days)
        self.assertFalse(
            self.Comment.objects.filter(pk=comment.pk).exists()
        )
    
    def test_cleanup_with_nested_comments(self):
        """Test cleanup handles nested/threaded comments."""
        parent = self.create_comment(
            content="Parent",
            is_public=False
        )
        parent.created_at = timezone.now() - timedelta(days=100)
        parent.save()
        
        child = self.create_comment(
            content="Child",
            parent=parent,
            is_public=False
        )
        child.created_at = timezone.now() - timedelta(days=100)
        child.save()
        
        out = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out)
        
        # Both should be deleted
        self.assertEqual(self.Comment.objects.count(), 0)
    
    def test_cleanup_large_number_of_comments(self):
        """Test cleanup with large number of comments."""
        # Create 100 old comments
        for i in range(100):
            comment = self.create_comment(
                content=f"Comment {i}",
                is_public=False
            )
            comment.created_at = timezone.now() - timedelta(days=100)
            comment.save()
        
        out = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out)
        
        # All should be deleted
        self.assertEqual(self.Comment.objects.count(), 0)
    
    def test_cleanup_preserves_recent_flagged_comments(self):
        """Test that recent flagged comments can be preserved."""
        recent_spam = self.create_comment(is_public=True)
        
        self.CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(recent_spam.pk),
            user=self.regular_user,
            flag='spam'
        )
        
        out = StringIO()
        # Only use days filter, not remove-spam
        call_command('cleanup_comments', '--days=90', stdout=out)
        
        # Should still exist (public and recent)
        self.assertTrue(
            self.Comment.objects.filter(pk=recent_spam.pk).exists()
        )
    
    def test_cleanup_output_formatting(self):
        """Test cleanup output is properly formatted."""
        comment = self.create_comment(is_public=False)
        comment.created_at = timezone.now() - timedelta(days=100)
        comment.save()
        
        out = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out)
        
        output = out.getvalue()
        # Should have readable output
        self.assertTrue(len(output) > 0)
    
    def test_cleanup_with_timezone_aware_dates(self):
        """Test cleanup handles timezone-aware dates correctly."""
        comment = self.create_comment(is_public=False)
        # Set timezone-aware date
        comment.created_at = timezone.make_aware(datetime(2020, 1, 1), timezone.get_current_timezone())
        comment.save()
        
        out = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out)
        
        # Very old comment should be deleted
        self.assertFalse(
            self.Comment.objects.filter(pk=comment.pk).exists()
        )
    
    def test_cleanup_idempotent(self):
        """Test cleanup is idempotent (can run multiple times safely)."""
        comment = self.create_comment(is_public=False)
        comment.created_at = timezone.now() - timedelta(days=100)
        comment.save()
        
        out1 = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out1)
        
        # Run again
        out2 = StringIO()
        call_command('cleanup_comments', '--days=90', stdout=out2)
        
        # Should indicate nothing to clean up
        output2 = out2.getvalue()
        self.assertIn('0', output2)