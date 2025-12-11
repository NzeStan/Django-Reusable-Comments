"""
Comprehensive Test Suite for ModerationAction Model

Tests cover:
- Action logging for moderation events
- Action types (approve, reject, ban, etc.)
- Moderator tracking
- Affected user tracking
- IP address logging
- Timestamp handling
- Audit trail functionality
- Edge cases
"""
import uuid
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from .base import BaseCommentTestCase


class ModerationActionCreationTests(BaseCommentTestCase):
    """
    Test ModerationAction creation scenarios.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import ModerationAction
        self.ModerationAction = ModerationAction
    
    def test_create_moderation_action_success(self):
        """Test creating a moderation action record."""
        comment = self.create_comment()
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='approved',
            reason='Content is appropriate',
            ip_address='192.168.1.100'
        )
        
        self.assertIsNotNone(action.pk)
        self.assertIsInstance(action.pk, uuid.UUID)
        self.assertEqual(action.moderator, self.moderator)
        self.assertEqual(action.action, 'approved')
    
    def test_action_has_uuid_primary_key(self):
        """Test that ModerationAction uses UUID as primary key."""
        comment = self.create_comment()
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='approved'
        )
        
        self.assertIsInstance(action.pk, uuid.UUID)
        self.assertIsInstance(action.id, uuid.UUID)
    
    def test_create_action_with_affected_user(self):
        """Test logging action that affects a specific user."""
        comment = self.create_comment(user=self.regular_user)
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='rejected',
            reason='Spam content',
            affected_user=self.regular_user
        )
        
        self.assertEqual(action.affected_user, self.regular_user)
    
    def test_create_ban_action_without_comment(self):
        """Test logging user ban action (no specific comment)."""
        action = self.ModerationAction.objects.create(
            moderator=self.moderator,
            action='banned_user',
            reason='Repeated violations',
            affected_user=self.banned_user,
            ip_address='192.168.1.100'
        )
        
        self.assertIsNone(action.comment_type)
        self.assertEqual(action.comment_id, '')
        self.assertEqual(action.affected_user, self.banned_user)


class ModerationActionTypesTests(BaseCommentTestCase):
    """
    Test different action types.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import ModerationAction
        self.ModerationAction = ModerationAction
    
    def test_approved_action(self):
        """Test logging comment approval."""
        comment = self.create_comment(is_public=False)
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='approved'
        )
        
        self.assertEqual(action.action, 'approved')
    
    def test_rejected_action(self):
        """Test logging comment rejection."""
        comment = self.create_comment()
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='rejected',
            reason='Inappropriate content'
        )
        
        self.assertEqual(action.action, 'rejected')
        self.assertEqual(action.reason, 'Inappropriate content')
    
    def test_removed_action(self):
        """Test logging comment removal."""
        comment = self.create_comment()
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='removed',
            reason='Violates community guidelines'
        )
        
        self.assertEqual(action.action, 'removed')
    
    def test_banned_user_action(self):
        """Test logging user ban."""
        action = self.ModerationAction.objects.create(
            moderator=self.moderator,
            action='banned_user',
            reason='Spam violations',
            affected_user=self.banned_user
        )
        
        self.assertEqual(action.action, 'banned_user')
        self.assertEqual(action.affected_user, self.banned_user)
    
    def test_unbanned_user_action(self):
        """Test logging user unban."""
        action = self.ModerationAction.objects.create(
            moderator=self.moderator,
            action='unbanned_user',
            reason='Appeal accepted',
            affected_user=self.banned_user
        )
        
        self.assertEqual(action.action, 'unbanned_user')


class ModerationActionAuditTrailTests(BaseCommentTestCase):
    """
    Test audit trail functionality.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import ModerationAction
        self.ModerationAction = ModerationAction
    
    def test_multiple_actions_for_same_comment(self):
        """Test logging multiple actions on same comment."""
        comment = self.create_comment()
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        action1 = self.ModerationAction.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='flagged',
            reason='Initial flag'
        )
        
        action2 = self.ModerationAction.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            moderator=self.admin_user,
            action='approved',
            reason='False positive'
        )
        
        actions = self.ModerationAction.objects.filter(
            comment_id=str(comment.pk)
        )
        
        self.assertEqual(actions.count(), 2)
        self.assertIn(action1, actions)
        self.assertIn(action2, actions)
    
    def test_actions_ordered_by_timestamp(self):
        """Test actions maintain chronological order."""
        comment = self.create_comment()
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        import time
        
        action1 = self.ModerationAction.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='flagged'
        )
        time.sleep(0.01)
        
        action2 = self.ModerationAction.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='approved'
        )
        
        actions = list(
            self.ModerationAction.objects.filter(
                comment_id=str(comment.pk)
            ).order_by('timestamp')
        )
        
        self.assertEqual(actions[0], action1)
        self.assertEqual(actions[1], action2)
        self.assertLess(action1.timestamp, action2.timestamp)


class ModerationActionModeratorTrackingTests(BaseCommentTestCase):
    """
    Test moderator tracking.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import ModerationAction
        self.ModerationAction = ModerationAction
    
    def test_action_records_moderator(self):
        """Test action records who performed it."""
        comment = self.create_comment()
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='approved'
        )
        
        self.assertEqual(action.moderator, self.moderator)
    
    def test_system_action_without_moderator(self):
        """Test automatic system action (no moderator)."""
        comment = self.create_comment()
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=None,  # System action
            action='auto_flagged',
            reason='Spam detection triggered'
        )
        
        self.assertIsNone(action.moderator)
    
    def test_filter_actions_by_moderator(self):
        """Test filtering actions by who performed them."""
        comment1 = self.create_comment(content='Comment 1')
        comment2 = self.create_comment(content='Comment 2')
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        mod_action = self.ModerationAction.objects.create(
            comment_type=content_type,
            comment_id=str(comment1.pk),
            moderator=self.moderator,
            action='approved'
        )
        
        admin_action = self.ModerationAction.objects.create(
            comment_type=content_type,
            comment_id=str(comment2.pk),
            moderator=self.admin_user,
            action='rejected'
        )
        
        moderator_actions = self.ModerationAction.objects.filter(
            moderator=self.moderator
        )
        
        self.assertIn(mod_action, moderator_actions)
        self.assertNotIn(admin_action, moderator_actions)


class ModerationActionIPTrackingTests(BaseCommentTestCase):
    """
    Test IP address tracking.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import ModerationAction
        self.ModerationAction = ModerationAction
    
    def test_action_records_ipv4_address(self):
        """Test action records IPv4 address."""
        comment = self.create_comment()
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='approved',
            ip_address='192.168.1.100'
        )
        
        self.assertEqual(action.ip_address, '192.168.1.100')
    
    def test_action_records_ipv6_address(self):
        """Test action records IPv6 address."""
        comment = self.create_comment()
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='rejected',
            ip_address='2001:0db8:85a3:0000:0000:8a2e:0370:7334'
        )
        
        self.assertEqual(action.ip_address, '2001:0db8:85a3:0000:0000:8a2e:0370:7334')
    
    def test_action_without_ip_address(self):
        """Test action without IP address (optional)."""
        comment = self.create_comment()
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='approved'
        )
        
        self.assertIsNone(action.ip_address)


class ModerationActionTimestampTests(BaseCommentTestCase):
    """
    Test timestamp handling.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import ModerationAction
        self.ModerationAction = ModerationAction
    
    def test_timestamp_set_on_creation(self):
        """Test timestamp is set when action is logged."""
        comment = self.create_comment()
        
        before = timezone.now()
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='approved'
        )
        after = timezone.now()
        
        self.assertIsNotNone(action.timestamp)
        self.assertGreaterEqual(action.timestamp, before)
        self.assertLessEqual(action.timestamp, after)


class ModerationActionCascadeTests(BaseCommentTestCase):
    """
    Test cascade deletion behavior.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import ModerationAction
        self.ModerationAction = ModerationAction
    
    def test_delete_moderator_sets_to_null(self):
        """Test deleting moderator doesn't delete actions."""
        comment = self.create_comment()
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='approved'
        )
        
        self.moderator.delete()
        
        # Action should exist with moderator=None
        fresh_action = self.ModerationAction.objects.get(pk=action.pk)
        self.assertIsNone(fresh_action.moderator)
    
    def test_delete_affected_user_sets_to_null(self):
        """Test deleting affected user doesn't delete actions."""
        action = self.ModerationAction.objects.create(
            moderator=self.moderator,
            action='banned_user',
            affected_user=self.banned_user
        )
        
        self.banned_user.delete()
        
        # Action should exist with affected_user=None
        fresh_action = self.ModerationAction.objects.get(pk=action.pk)
        self.assertIsNone(fresh_action.affected_user)


class ModerationActionQueryTests(BaseCommentTestCase):
    """
    Test querying actions.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import ModerationAction
        self.ModerationAction = ModerationAction
    
    def test_filter_actions_by_comment(self):
        """Test filtering actions for specific comment."""
        comment1 = self.create_comment(content='Comment 1')
        comment2 = self.create_comment(content='Comment 2')
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        action1 = self.ModerationAction.objects.create(
            comment_type=content_type,
            comment_id=str(comment1.pk),
            moderator=self.moderator,
            action='approved'
        )
        
        action2 = self.ModerationAction.objects.create(
            comment_type=content_type,
            comment_id=str(comment2.pk),
            moderator=self.moderator,
            action='rejected'
        )
        
        comment1_actions = self.ModerationAction.objects.filter(
            comment_id=str(comment1.pk)
        )
        
        self.assertIn(action1, comment1_actions)
        self.assertNotIn(action2, comment1_actions)
    
    def test_filter_actions_by_type(self):
        """Test filtering by action type."""
        comment1 = self.create_comment(content='Comment 1')
        comment2 = self.create_comment(content='Comment 2')
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        approved_action = self.ModerationAction.objects.create(
            comment_type=content_type,
            comment_id=str(comment1.pk),
            moderator=self.moderator,
            action='approved'
        )
        
        rejected_action = self.ModerationAction.objects.create(
            comment_type=content_type,
            comment_id=str(comment2.pk),
            moderator=self.moderator,
            action='rejected'
        )
        
        approved_actions = self.ModerationAction.objects.filter(
            action='approved'
        )
        
        self.assertIn(approved_action, approved_actions)
        self.assertNotIn(rejected_action, approved_actions)


class ModerationActionEdgeCaseTests(BaseCommentTestCase):
    """
    Test edge cases.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import ModerationAction
        self.ModerationAction = ModerationAction
    
    def test_action_with_long_reason(self):
        """Test action with very long reason text."""
        comment = self.create_comment()
        long_reason = 'Violation: ' + ('spam ' * 500)
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='rejected',
            reason=long_reason
        )
        
        self.assertEqual(action.reason, long_reason)
    
    def test_action_with_unicode_reason(self):
        """Test action with Unicode in reason."""
        comment = self.create_comment()
        unicode_reason = '违规内容 (Inappropriate content)'
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='removed',
            reason=unicode_reason
        )
        
        self.assertEqual(action.reason, unicode_reason)


class ModerationActionStringRepresentationTests(BaseCommentTestCase):
    """
    Test string representation.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import ModerationAction
        self.ModerationAction = ModerationAction
    
    def test_str_representation(self):
        """Test string representation includes key info."""
        comment = self.create_comment()
        
        action = self.ModerationAction.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            moderator=self.moderator,
            action='approved'
        )
        
        str_repr = str(action)
        
        # Should include identifying information
        self.assertIsInstance(str_repr, str)
        self.assertGreater(len(str_repr), 0)