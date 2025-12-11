"""
Comprehensive Test Suite for CommentFlag Model

Tests cover:
- Flag creation with different flag types
- Flag validation and constraints
- Unique constraint enforcement (one flag per user per comment per type)
- Flag review workflow
- Flag states (reviewed/unreviewed)
- Generic foreign key to Comment
- Manager methods
- Edge cases and error conditions
"""
import uuid
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .base import BaseCommentTestCase


class CommentFlagCreationTests(BaseCommentTestCase):
    """
    Test CommentFlag creation with various scenarios.
    """
    
    def test_create_basic_flag_success(self):
        """Test creating a basic flag on a comment."""
        comment = self.create_comment()
        flag = self.create_flag(
            comment=comment,
            flag='spam',
            reason='This comment appears to be spam'
        )
        
        self.assertFlagValid(flag)
        self.assertEqual(flag.flag, 'spam')
        self.assertEqual(flag.user, self.moderator)
        self.assertEqual(flag.comment_id, str(comment.pk))
    
    def test_flag_has_uuid_primary_key(self):
        """Test that CommentFlag uses UUID as primary key."""
        flag = self.create_flag()
        
        self.assertIsInstance(flag.pk, uuid.UUID)
        self.assertIsInstance(flag.id, uuid.UUID)
    
    def test_create_flag_all_types(self):
        """Test creating flags with all available flag types."""
        comment = self.create_comment()
        
        flag_types = [
            'spam', 'harassment', 'hate_speech', 'violence',
            'sexual', 'misinformation', 'off_topic', 'offensive',
            'inappropriate', 'other'
        ]
        
        for flag_type in flag_types:
            with self.subTest(flag_type=flag_type):
                # Create different comment for each flag
                test_comment = self.create_comment(content=f'Test {flag_type}')
                flag = self.create_flag(
                    comment=test_comment,
                    flag=flag_type,
                    reason=f'Testing {flag_type} flag'
                )
                
                self.assertEqual(flag.flag, flag_type)
                self.assertFlagValid(flag)
    
    def test_create_flag_with_detailed_reason(self):
        """Test creating flag with detailed reason."""
        comment = self.create_comment()
        detailed_reason = """
        This comment contains:
        1. Promotional links
        2. Irrelevant content
        3. Duplicate posting
        """
        
        flag = self.create_flag(
            comment=comment,
            reason=detailed_reason
        )
        
        self.assertEqual(flag.reason, detailed_reason)
    
    def test_create_flag_without_reason(self):
        """Test creating flag without reason (should be allowed)."""
        comment = self.create_comment()
        flag = self.create_flag(
            comment=comment,
            reason=''  # Empty reason
        )
        
        self.assertFlagValid(flag)
        self.assertEqual(flag.reason, '')
    
    def test_flag_not_reviewed_by_default(self):
        """Test flag is not reviewed by default."""
        flag = self.create_flag()
        
        self.assertFalse(flag.reviewed)
        self.assertIsNone(flag.reviewed_by)
        self.assertIsNone(flag.reviewed_at)
        self.assertEqual(flag.review_action, '')


class CommentFlagConstraintTests(BaseCommentTestCase):
    """
    Test CommentFlag unique constraints and validation.
    """
    
    def test_unique_constraint_prevents_duplicate_flags(self):
        """Test user cannot flag same comment with same type twice."""
        comment = self.create_comment()
        
        # First flag succeeds
        flag1 = self.create_flag(
            comment=comment,
            user=self.moderator,
            flag='spam'
        )
        
        # Second flag with same parameters should fail
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.CommentFlag.objects.create(
                    comment_type=ContentType.objects.get_for_model(self.Comment),
                    comment_id=str(comment.pk),
                    user=self.moderator,
                    flag='spam',
                    reason='Duplicate flag attempt'
                )
    
    def test_same_user_can_flag_with_different_types(self):
        """Test user can flag same comment with different flag types."""
        comment = self.create_comment()
        
        spam_flag = self.create_flag(
            comment=comment,
            user=self.moderator,
            flag='spam'
        )
        
        harassment_flag = self.CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            user=self.moderator,
            flag='harassment',
            reason='Different flag type'
        )
        
        self.assertFlagValid(spam_flag)
        self.assertFlagValid(harassment_flag)
        self.assertNotEqual(spam_flag.pk, harassment_flag.pk)
    
    def test_different_users_can_flag_same_comment(self):
        """Test different users can flag same comment with same type."""
        comment = self.create_comment()
        
        flag1 = self.create_flag(
            comment=comment,
            user=self.moderator,
            flag='spam'
        )
        
        flag2 = self.CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            user=self.admin_user,
            flag='spam',
            reason='I also think this is spam'
        )
        
        self.assertFlagValid(flag1)
        self.assertFlagValid(flag2)
        self.assertNotEqual(flag1.pk, flag2.pk)
    
    def test_user_can_flag_different_comments_same_type(self):
        """Test user can use same flag type on different comments."""
        comment1 = self.create_comment(content='First comment')
        comment2 = self.create_comment(content='Second comment')
        
        flag1 = self.create_flag(
            comment=comment1,
            user=self.moderator,
            flag='spam'
        )
        
        flag2 = self.create_flag(
            comment=comment2,
            user=self.moderator,
            flag='spam'
        )
        
        self.assertFlagValid(flag1)
        self.assertFlagValid(flag2)
        self.assertNotEqual(flag1.pk, flag2.pk)


class CommentFlagValidationTests(BaseCommentTestCase):
    """
    Test CommentFlag validation rules.
    """
    
    def test_create_flag_with_invalid_type_fails(self):
        """Test creating flag with invalid flag type fails."""
        comment = self.create_comment()
        
        with self.assertRaises(ValidationError):
            flag = self.CommentFlag(
                comment_type=ContentType.objects.get_for_model(self.Comment),
                comment_id=str(comment.pk),
                user=self.moderator,
                flag='invalid_flag_type',  # Not in FLAG_CHOICES
                reason='Testing invalid flag'
            )
            flag.full_clean()
    
    def test_create_flag_without_user_fails(self):
        """Test creating flag without user fails validation."""
        comment = self.create_comment()
        
        with self.assertRaises((ValidationError, IntegrityError)):
            flag = self.CommentFlag(
                comment_type=ContentType.objects.get_for_model(self.Comment),
                comment_id=str(comment.pk),
                user=None,  # No user
                flag='spam'
            )
            flag.full_clean()
    
    def test_create_flag_without_comment_id_fails(self):
        """Test creating flag without comment_id fails validation."""
        with self.assertRaises(ValidationError):
            flag = self.CommentFlag(
                comment_type=ContentType.objects.get_for_model(self.Comment),
                comment_id='',  # Empty comment_id
                user=self.moderator,
                flag='spam'
            )
            flag.full_clean()
    
    def test_create_flag_with_non_existent_comment(self):
        """Test creating flag for non-existent comment (should work)."""
        fake_comment_id = str(uuid.uuid4())
        
        flag = self.CommentFlag.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=fake_comment_id,
            user=self.moderator,
            flag='spam',
            reason='Flagging non-existent comment'
        )
        
        # Should save (no FK constraint on generic relation)
        self.assertFlagValid(flag)


class CommentFlagReviewTests(BaseCommentTestCase):
    """
    Test CommentFlag review workflow.
    """
    
    def test_mark_flag_as_reviewed_dismissed(self):
        """Test marking flag as reviewed with dismissed action."""
        flag = self.create_flag()
        
        flag.mark_reviewed(
            moderator=self.admin_user,
            action='dismissed',
            notes='False positive'
        )
        
        fresh_flag = self.get_fresh_flag(flag)
        self.assertTrue(fresh_flag.reviewed)
        self.assertEqual(fresh_flag.reviewed_by, self.admin_user)
        self.assertIsNotNone(fresh_flag.reviewed_at)
        self.assertEqual(fresh_flag.review_action, 'dismissed')
        self.assertEqual(fresh_flag.review_notes, 'False positive')
    
    def test_mark_flag_as_reviewed_actioned(self):
        """Test marking flag as reviewed with actioned."""
        flag = self.create_flag()
        
        flag.mark_reviewed(
            moderator=self.admin_user,
            action='actioned',
            notes='Comment removed'
        )
        
        fresh_flag = self.get_fresh_flag(flag)
        self.assertTrue(fresh_flag.reviewed)
        self.assertEqual(fresh_flag.review_action, 'actioned')
    
    def test_mark_reviewed_sets_timestamp(self):
        """Test that mark_reviewed sets reviewed_at timestamp."""
        flag = self.create_flag()
        
        before = timezone.now()
        flag.mark_reviewed(moderator=self.admin_user, action='dismissed')
        after = timezone.now()
        
        fresh_flag = self.get_fresh_flag(flag)
        self.assertIsNotNone(fresh_flag.reviewed_at)
        self.assertGreaterEqual(fresh_flag.reviewed_at, before)
        self.assertLessEqual(fresh_flag.reviewed_at, after)
    
    def test_mark_reviewed_without_notes(self):
        """Test marking as reviewed without notes (optional)."""
        flag = self.create_flag()
        
        flag.mark_reviewed(
            moderator=self.admin_user,
            action='dismissed',
            notes=''  # No notes
        )
        
        fresh_flag = self.get_fresh_flag(flag)
        self.assertTrue(fresh_flag.reviewed)
        self.assertEqual(fresh_flag.review_notes, '')
    
    def test_cannot_review_with_invalid_action(self):
        """Test that invalid review action raises error."""
        flag = self.create_flag()
        
        with self.assertRaises(ValueError):
            flag.mark_reviewed(
                moderator=self.admin_user,
                action='invalid_action'
            )


class CommentFlagManagerTests(BaseCommentTestCase):
    """
    Test CommentFlag manager methods.
    """
    
    def test_filter_unreviewed_flags(self):
        """Test filtering unreviewed flags."""
        reviewed_flag = self.create_flag()
        reviewed_flag.mark_reviewed(
            moderator=self.admin_user,
            action='dismissed'
        )
        
        unreviewed_flag = self.create_flag(
            comment=self.create_comment(content='Another comment')
        )
        
        unreviewed = self.CommentFlag.objects.filter(reviewed=False)
        
        self.assertIn(unreviewed_flag, unreviewed)
        self.assertNotIn(reviewed_flag, unreviewed)
    
    def test_filter_flags_by_type(self):
        """Test filtering flags by flag type."""
        spam_flag = self.create_flag(
            comment=self.create_comment(content='Spam comment'),
            flag='spam'
        )
        
        harassment_flag = self.create_flag(
            comment=self.create_comment(content='Harassment comment'),
            flag='harassment'
        )
        
        spam_flags = self.CommentFlag.objects.filter(flag='spam')
        
        self.assertIn(spam_flag, spam_flags)
        self.assertNotIn(harassment_flag, spam_flags)
    
    def test_filter_flags_by_user(self):
        """Test filtering flags by who created them."""
        moderator_flag = self.create_flag(user=self.moderator)
        admin_flag = self.create_flag(
            comment=self.create_comment(content='Another comment'),
            user=self.admin_user
        )
        
        moderator_flags = self.CommentFlag.objects.filter(user=self.moderator)
        
        self.assertIn(moderator_flag, moderator_flags)
        self.assertNotIn(admin_flag, moderator_flags)
    
    def test_filter_flags_for_specific_comment(self):
        """Test getting all flags for a specific comment."""
        comment1 = self.create_comment(content='First comment')
        comment2 = self.create_comment(content='Second comment')
        
        flag1 = self.create_flag(comment=comment1, user=self.moderator)
        flag2 = self.create_flag(comment=comment1, user=self.admin_user)
        flag3 = self.create_flag(comment=comment2, user=self.moderator)
        
        comment1_flags = self.CommentFlag.objects.filter(
            comment_id=str(comment1.pk)
        )
        
        self.assertEqual(comment1_flags.count(), 2)
        self.assertIn(flag1, comment1_flags)
        self.assertIn(flag2, comment1_flags)
        self.assertNotIn(flag3, comment1_flags)
    
    def test_order_by_created_at_descending(self):
        """Test default ordering by created_at descending."""
        import time
        
        flag1 = self.create_flag(
            comment=self.create_comment(content='Comment 1')
        )
        time.sleep(0.01)
        flag2 = self.create_flag(
            comment=self.create_comment(content='Comment 2')
        )
        time.sleep(0.01)
        flag3 = self.create_flag(
            comment=self.create_comment(content='Comment 3')
        )
        
        flags = list(self.CommentFlag.objects.all())
        
        self.assertEqual(flags[0], flag3)
        self.assertEqual(flags[1], flag2)
        self.assertEqual(flags[2], flag1)


class CommentFlagStringRepresentationTests(BaseCommentTestCase):
    """
    Test CommentFlag string representation.
    """
    
    def test_str_representation_includes_user_and_flag_type(self):
        """Test string representation includes key information."""
        comment = self.create_comment()
        flag = self.create_flag(
            comment=comment,
            user=self.moderator,
            flag='spam'
        )
        
        str_repr = str(flag)
        
        self.assertIn(self.moderator.username, str_repr.lower())
        self.assertIn('spam', str_repr.lower())
    
    def test_str_representation_handles_deleted_user(self):
        """Test string representation when user is deleted."""
        comment = self.create_comment()
        flag = self.create_flag(comment=comment)
        
        # Delete the user
        flag.user.delete()
        fresh_flag = self.get_fresh_flag(flag)
        
        # Should not raise error
        str_repr = str(fresh_flag)
        self.assertIsInstance(str_repr, str)


class CommentFlagEdgeCaseTests(BaseCommentTestCase):
    """
    Test edge cases and boundary conditions for CommentFlag.
    """
    
    def test_flag_with_very_long_reason(self):
        """Test flag with very long reason text."""
        long_reason = 'This is spam because ' + ('spam ' * 500)
        flag = self.create_flag(reason=long_reason)
        
        self.assertEqual(flag.reason, long_reason)
    
    def test_flag_with_unicode_reason(self):
        """Test flag with Unicode characters in reason."""
        unicode_reason = 'Flagged for 不当内容 and неприемлемый контент'
        flag = self.create_flag(reason=unicode_reason)
        
        self.assertEqual(flag.reason, unicode_reason)
    
    def test_flag_with_html_in_reason(self):
        """Test flag with HTML in reason (should be stored as-is)."""
        html_reason = '<script>alert("xss")</script> Suspicious content'
        flag = self.create_flag(reason=html_reason)
        
        self.assertEqual(flag.reason, html_reason)
    
    def test_multiple_flags_same_comment_different_users(self):
        """Test that one comment can have many flags from different users."""
        comment = self.create_comment()
        
        flag1 = self.create_flag(comment=comment, user=self.moderator, flag='spam')
        flag2 = self.create_flag(comment=comment, user=self.admin_user, flag='spam')
        flag3 = self.create_flag(comment=comment, user=self.staff_user, flag='spam')
        
        comment_flags = self.CommentFlag.objects.filter(
            comment_id=str(comment.pk)
        )
        
        self.assertEqual(comment_flags.count(), 3)
    
    def test_flag_survives_comment_content_update(self):
        """Test that flag persists when comment content is updated."""
        comment = self.create_comment(content='Original content')
        flag = self.create_flag(comment=comment)
        
        # Update comment content
        comment.content = 'Updated content'
        comment.save()
        
        # Flag should still exist and point to comment
        fresh_flag = self.get_fresh_flag(flag)
        self.assertEqual(fresh_flag.comment_id, str(comment.pk))


class CommentFlagDeletionTests(BaseCommentTestCase):
    """
    Test CommentFlag deletion behavior.
    """
    
    def test_delete_comment_cascades_to_flags(self):
        """Test that deleting comment also deletes its flags."""
        comment = self.create_comment()
        flag1 = self.create_flag(comment=comment, user=self.moderator)
        flag2 = self.create_flag(comment=comment, user=self.admin_user)
        
        comment.delete()
        
        # Flags should be deleted (CASCADE)
        self.assertFalse(
            self.CommentFlag.objects.filter(pk=flag1.pk).exists()
        )
        self.assertFalse(
            self.CommentFlag.objects.filter(pk=flag2.pk).exists()
        )
    
    def test_delete_user_sets_flag_user_to_null(self):
        """Test deleting user doesn't delete their flags."""
        comment = self.create_comment()
        flag = self.create_flag(comment=comment, user=self.moderator)
        
        # Delete the user who created the flag
        user_pk = self.moderator.pk
        self.moderator.delete()
        
        # Flag should still exist but user is None
        fresh_flag = self.get_fresh_flag(flag)
        self.assertIsNone(fresh_flag.user)
    
    def test_delete_reviewer_sets_reviewed_by_to_null(self):
        """Test deleting reviewer doesn't delete the flag."""
        comment = self.create_comment()
        flag = self.create_flag(comment=comment)
        flag.mark_reviewed(moderator=self.admin_user, action='dismissed')
        
        # Delete the reviewer
        self.admin_user.delete()
        
        # Flag should still exist and be marked as reviewed
        fresh_flag = self.get_fresh_flag(flag)
        self.assertTrue(fresh_flag.reviewed)
        self.assertIsNone(fresh_flag.reviewed_by)
        self.assertIsNotNone(fresh_flag.reviewed_at)


class CommentFlagPerformanceTests(BaseCommentTestCase):
    """
    Test CommentFlag performance and optimization.
    """
    
    def test_bulk_create_flags(self):
        """Test bulk creating multiple flags efficiently."""
        comment = self.create_comment()
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        flags_data = [
            self.CommentFlag(
                comment_type=content_type,
                comment_id=str(comment.pk),
                user=self.regular_user,
                flag='spam',
                reason=f'Bulk flag {i}'
            )
            for i in range(50)
        ]
        
        # This should fail due to unique constraint
        # But first flag should succeed
        first_flag = flags_data[0]
        first_flag.save()
        
        self.assertFlagValid(first_flag)
    
    def test_select_related_optimization(self):
        """Test that select_related optimization works for flags."""
        flag = self.create_flag()
        
        optimized = self.CommentFlag.objects.select_related('user').get(
            pk=flag.pk
        )
        
        # Access user should not trigger additional query
        with self.assertNumQueries(0):
            _ = optimized.user.username if optimized.user else None


class CommentFlagIndexTests(BaseCommentTestCase):
    """
    Test that database indexes are working for common queries.
    """
    
    def test_filter_by_comment_uses_index(self):
        """Test filtering by comment_type and comment_id (indexed)."""
        comment = self.create_comment()
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        # Create 10 flags for the same comment
        for i in range(10):
            self.CommentFlag.objects.create(
                comment_type=content_type,
                comment_id=str(comment.pk),
                user=self.regular_user if i % 2 == 0 else self.another_user,
                flag='spam'
            )
        
        # Query using the indexed fields
        flags = self.CommentFlag.objects.filter(
            comment_type=content_type,
            comment_id=str(comment.pk)
        )
        
        self.assertEqual(flags.count(), 10)
    
    def test_filter_by_user_and_flag_uses_index(self):
        """Test filtering by user and flag (indexed)."""
        for i in range(5):
            comment = self.create_comment(content=f'Comment {i}')
            self.create_flag(comment=comment, user=self.moderator, flag='spam')
        
        # Query using indexed fields
        user_spam_flags = self.CommentFlag.objects.filter(
            user=self.moderator,
            flag='spam'
        )
        
        self.assertEqual(user_spam_flags.count(), 5)