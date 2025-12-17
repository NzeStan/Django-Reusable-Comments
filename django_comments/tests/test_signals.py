"""
Comprehensive tests for django_comments/signals.py

Tests cover:
- All custom signals (pre_save, post_save, pre_delete, post_delete, flagged, approved, rejected)
- Signal receivers and forwarding
- Helper functions (flag_comment, approve_comment, reject_comment, trigger_notifications, safe_send)
- Automatic flag application
- Notification triggering
- Integration scenarios
- Error handling and edge cases
- Real-world scenarios with Unicode and special characters

All tests properly handle:
- Signal connection/disconnection
- Fresh instances for settings tests
- Proper test object setup
- Unicode and special characters
- Edge cases and boundary conditions
"""
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import signals
from django.dispatch import receiver, Signal
from unittest.mock import Mock, patch, MagicMock, call
from datetime import timedelta
import logging

from django_comments.tests.base import BaseCommentTestCase
from django_comments import signals as comment_signals
from django_comments.signals import (
    # Signals
    comment_pre_save,
    comment_post_save,
    comment_pre_delete,
    comment_post_delete,
    comment_flagged,
    comment_approved,
    comment_rejected,
    # Helper functions
    safe_send,
    trigger_notifications,
    flag_comment,
    approve_comment,
    reject_comment,
    # Receivers
    on_comment_pre_save,
    on_comment_post_save,
    on_comment_pre_delete,
    on_comment_post_delete,
)
from django_comments.conf import comments_settings
from django_comments.models import CommentFlag, ModerationAction, BannedUser

User = get_user_model()


# ============================================================================
# TEST MIXINS AND HELPERS
# ============================================================================

class SignalTestMixin:
    """Mixin for signal testing with proper cleanup and signal tracking."""
    
    def setUp(self):
        super().setUp()
        self.signal_receivers = []
        self._builtin_receivers_disconnected = False
    
    def tearDown(self):
        # Disconnect all test signal receivers
        for signal_obj, receiver_func in self.signal_receivers:
            signal_obj.disconnect(receiver_func)
        
        # Reconnect built-in receivers if they were disconnected
        if self._builtin_receivers_disconnected:
            self.reconnect_builtin_receivers()
        
        super().tearDown()
    
    def disconnect_builtin_receivers(self):
        """Disconnect built-in signal receivers (on_comment_pre_save, etc.)."""
        signals.pre_save.disconnect(on_comment_pre_save, sender=self.Comment)
        signals.post_save.disconnect(on_comment_post_save, sender=self.Comment)
        signals.pre_delete.disconnect(on_comment_pre_delete, sender=self.Comment)
        signals.post_delete.disconnect(on_comment_post_delete, sender=self.Comment)
        self._builtin_receivers_disconnected = True
    
    def reconnect_builtin_receivers(self):
        """Reconnect built-in signal receivers."""
        signals.pre_save.connect(on_comment_pre_save, sender=self.Comment)
        signals.post_save.connect(on_comment_post_save, sender=self.Comment)
        signals.pre_delete.connect(on_comment_pre_delete, sender=self.Comment)
        signals.post_delete.connect(on_comment_post_delete, sender=self.Comment)
        self._builtin_receivers_disconnected = False
    
    def create_signal_receiver(self, signal_obj):
        """
        Create a mock receiver for a signal and track calls.
        
        Returns:
            Mock object that tracks signal calls
        """
        mock_receiver = Mock()
        
        def receiver_wrapper(sender, **kwargs):
            mock_receiver(sender=sender, **kwargs)
        
        signal_obj.connect(receiver_wrapper)
        self.signal_receivers.append((signal_obj, receiver_wrapper))
        
        return mock_receiver


# ============================================================================
# SAFE_SEND FUNCTION TESTS
# ============================================================================

class SafeSendTests(SignalTestMixin, BaseCommentTestCase):
    """Test the safe_send utility function."""
    
    def setUp(self):
        super().setUp()
        # Disconnect built-in receivers to test safe_send in isolation
        self.disconnect_builtin_receivers()
    
    def test_safe_send_removes_signal_kwarg(self):
        """Test safe_send removes 'signal' from extra_kwargs to avoid conflicts."""
        mock_receiver = self.create_signal_receiver(comment_pre_save)
        
        comment = self.create_comment(content="Test")
        
        # Call safe_send with 'signal' in extra_kwargs
        # This would normally cause a conflict, but safe_send removes it first
        try:
            safe_send(
                comment_pre_save,
                sender=self.Comment,
                comment=comment,
                signal='should_be_removed'  # This gets removed by safe_send
            )
            # If we got here, safe_send successfully prevented the error
            success = True
        except TypeError as e:
            # If we get TypeError about duplicate signal kwarg, safe_send failed
            success = False
        
        self.assertTrue(success, "safe_send should prevent signal kwarg conflicts")
        
        # Verify signal was sent and comment was passed
        self.assertEqual(mock_receiver.call_count, 1)
        call_kwargs = mock_receiver.call_args[1]
        self.assertIn('comment', call_kwargs)
        # Note: Django ALWAYS adds 'signal' kwarg to receivers - that's expected behavior
    
    def test_safe_send_preserves_other_kwargs(self):
        """Test safe_send preserves all other kwargs."""
        mock_receiver = self.create_signal_receiver(comment_flagged)
        
        comment = self.create_comment(content="Test")
        
        safe_send(
            comment_flagged,
            sender=CommentFlag,
            comment=comment,
            user=self.regular_user,
            flag_type='spam',
            reason='Test reason',
            extra_data='extra'
        )
        
        call_kwargs = mock_receiver.call_args[1]
        self.assertEqual(call_kwargs['comment'], comment)
        self.assertEqual(call_kwargs['user'], self.regular_user)
        self.assertEqual(call_kwargs['flag_type'], 'spam')
        self.assertEqual(call_kwargs['reason'], 'Test reason')
        self.assertEqual(call_kwargs['extra_data'], 'extra')
    
    def test_safe_send_with_no_extra_kwargs(self):
        """Test safe_send works with no extra kwargs."""
        mock_receiver = self.create_signal_receiver(comment_pre_save)
        
        comment = self.create_comment(content="Test")
        
        safe_send(comment_pre_save, sender=self.Comment, comment=comment)
        
        self.assertEqual(mock_receiver.call_count, 1)


# ============================================================================
# CUSTOM SIGNAL TESTS
# ============================================================================

class CustomSignalTests(SignalTestMixin, BaseCommentTestCase):
    """Test custom Django signals are properly defined and can be used."""
    
    def test_comment_pre_save_signal_exists(self):
        """Test comment_pre_save signal exists and is a Signal instance."""
        self.assertIsInstance(comment_pre_save, Signal)
    
    def test_comment_post_save_signal_exists(self):
        """Test comment_post_save signal exists."""
        self.assertIsInstance(comment_post_save, Signal)
    
    def test_comment_pre_delete_signal_exists(self):
        """Test comment_pre_delete signal exists."""
        self.assertIsInstance(comment_pre_delete, Signal)
    
    def test_comment_post_delete_signal_exists(self):
        """Test comment_post_delete signal exists."""
        self.assertIsInstance(comment_post_delete, Signal)
    
    def test_comment_flagged_signal_exists(self):
        """Test comment_flagged signal exists."""
        self.assertIsInstance(comment_flagged, Signal)
    
    def test_comment_approved_signal_exists(self):
        """Test comment_approved signal exists."""
        self.assertIsInstance(comment_approved, Signal)
    
    def test_comment_rejected_signal_exists(self):
        """Test comment_rejected signal exists."""
        self.assertIsInstance(comment_rejected, Signal)
    
    def test_signals_can_connect_receivers(self):
        """Test signals can have receivers connected."""
        for signal_obj in [comment_pre_save, comment_post_save, comment_pre_delete,
                          comment_post_delete, comment_flagged, comment_approved,
                          comment_rejected]:
            mock_receiver = self.create_signal_receiver(signal_obj)
            
            # Trigger signal manually
            signal_obj.send(sender=self.Comment, test_data='test')
            
            # Verify receiver was called
            self.assertEqual(mock_receiver.call_count, 1)


# ============================================================================
# SIGNAL RECEIVER TESTS
# ============================================================================

class SignalReceiverTests(SignalTestMixin, BaseCommentTestCase):
    """Test signal receivers forward to custom signals correctly."""
    
    def test_pre_save_receiver_forwards_to_custom_signal(self):
        """Test on_comment_pre_save forwards to comment_pre_save."""
        mock_receiver = self.create_signal_receiver(comment_pre_save)
        
        comment = self.create_comment(content="Test")
        
        # Verify custom signal was sent
        self.assertEqual(mock_receiver.call_count, 1)
        call_kwargs = mock_receiver.call_args[1]
        self.assertEqual(call_kwargs['comment'], comment)
    
    def test_post_save_receiver_forwards_to_custom_signal(self):
        """Test on_comment_post_save forwards to comment_post_save."""
        mock_receiver = self.create_signal_receiver(comment_post_save)
        
        comment = self.create_comment(content="Test")
        
        # Verify custom signal was sent
        self.assertEqual(mock_receiver.call_count, 1)
        call_kwargs = mock_receiver.call_args[1]
        self.assertEqual(call_kwargs['comment'], comment)
        self.assertEqual(call_kwargs['created'], True)
    
    def test_pre_delete_receiver_forwards_to_custom_signal(self):
        """Test on_comment_pre_delete forwards to comment_pre_delete."""
        mock_receiver = self.create_signal_receiver(comment_pre_delete)
        
        comment = self.create_comment(content="Test")
        comment.delete()
        
        # Verify custom signal was sent
        self.assertEqual(mock_receiver.call_count, 1)
        call_kwargs = mock_receiver.call_args[1]
        self.assertEqual(call_kwargs['comment'], comment)
    
    def test_post_delete_receiver_forwards_to_custom_signal(self):
        """Test on_comment_post_delete forwards to comment_post_delete."""
        mock_receiver = self.create_signal_receiver(comment_post_delete)
        
        comment = self.create_comment(content="Test")
        comment.delete()
        
        # Verify custom signal was sent
        self.assertEqual(mock_receiver.call_count, 1)
        call_kwargs = mock_receiver.call_args[1]
        self.assertEqual(call_kwargs['comment'], comment)
    
    def test_post_save_with_update_not_created(self):
        """Test post_save signal with created=False on update."""
        mock_receiver = self.create_signal_receiver(comment_post_save)
        
        comment = self.create_comment(content="Original")
        mock_receiver.reset_mock()  # Reset after creation
        
        # Update comment
        comment.content = "Updated"
        comment.save()
        
        # Verify signal was sent with created=False
        self.assertEqual(mock_receiver.call_count, 1)
        call_kwargs = mock_receiver.call_args[1]
        self.assertEqual(call_kwargs['created'], False)


# ============================================================================
# POST_SAVE AUTOMATIC FLAGS TESTS
# ============================================================================

class PostSaveAutomaticFlagsTests(SignalTestMixin, BaseCommentTestCase):
    """Test automatic flag application on comment post_save."""
    
    @patch('django_comments.utils.apply_automatic_flags')
    def test_automatic_flags_called_on_create(self, mock_apply_flags):
        """Test apply_automatic_flags is called when comment is created."""
        comment = self.create_comment(content="Test spam content")
        
        # Verify automatic flags were attempted
        mock_apply_flags.assert_called_once_with(comment)
    
    @patch('django_comments.utils.apply_automatic_flags')
    def test_automatic_flags_not_called_on_update(self, mock_apply_flags):
        """Test apply_automatic_flags is NOT called when comment is updated."""
        comment = self.create_comment(content="Original")
        mock_apply_flags.reset_mock()
        
        comment.content = "Updated"
        comment.save()
        
        # Should not be called on update
        mock_apply_flags.assert_not_called()
    
    @patch('django_comments.utils.apply_automatic_flags', side_effect=Exception('Flag error'))
    def test_automatic_flags_error_logged(self, mock_apply_flags):
        """Test errors in automatic flagging are logged but don't break save."""
        with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
            comment = self.create_comment(content="Test")
            
            # Comment should still be created
            self.assertIsNotNone(comment.pk)
            
            # Error should be logged
            self.assertTrue(any('Failed to apply automatic flags' in log for log in logs.output))


# ============================================================================
# TRIGGER_NOTIFICATIONS TESTS
# ============================================================================

class TriggerNotificationsTests(SignalTestMixin, BaseCommentTestCase):
    """Test trigger_notifications function."""
    
    @patch('django_comments.notifications.notify_new_comment')
    def test_notifications_disabled_returns_early(self, mock_notify):
        """Test trigger_notifications returns early when disabled."""
        # Patch settings directly to disable notifications
        with patch.object(comments_settings, 'SEND_NOTIFICATIONS', False):
            # When notifications are disabled, creating a comment shouldn't trigger notifications
            comment = self.create_comment(content="Test")
            
            # Should not call notification functions
            mock_notify.assert_not_called()
    
    @override_settings(COMMENTS={'SEND_NOTIFICATIONS': True})
    @patch('django_comments.notifications.notify_new_comment')
    def test_new_comment_notification_sent(self, mock_notify):
        """Test new comment triggers notify_new_comment."""
        # Creating a comment triggers post_save signal which calls trigger_notifications
        comment = self.create_comment(content="Test")
        
        mock_notify.assert_called_once_with(comment)
    
    @override_settings(COMMENTS={'SEND_NOTIFICATIONS': True})
    @patch('django_comments.notifications.notify_comment_reply')
    def test_reply_notification_sent(self, mock_notify_reply):
        """Test reply to comment triggers notify_comment_reply."""
        parent = self.create_comment(content="Parent comment")
        mock_notify_reply.reset_mock()  # Reset after parent creation
        
        reply = self.create_comment(content="Reply", parent=parent)
        
        mock_notify_reply.assert_called_once_with(reply, parent_comment=parent)
    
    @override_settings(COMMENTS={
        'SEND_NOTIFICATIONS': True,
        'MODERATOR_REQUIRED': True
    })
    @patch('django_comments.notifications.notify_moderators')
    def test_moderator_notification_for_non_public(self, mock_notify_mods):
        """Test moderator notification sent for non-public comments when required."""
        comment = self.create_comment(content="Pending comment", is_public=False)
        
        mock_notify_mods.assert_called_once_with(comment)
    
    @override_settings(COMMENTS={
        'SEND_NOTIFICATIONS': True,
        'MODERATOR_REQUIRED': True
    })
    @patch('django_comments.notifications.notify_moderators')
    def test_no_moderator_notification_for_public(self, mock_notify_mods):
        """Test no moderator notification for public comments."""
        comment = self.create_comment(content="Public comment", is_public=True)
        
        # Should not notify moderators for public comments
        mock_notify_mods.assert_not_called()
    
    @override_settings(COMMENTS={'SEND_NOTIFICATIONS': True})
    @patch('django_comments.notifications.notify_new_comment')
    def test_no_notifications_for_update(self, mock_notify):
        """Test no notifications sent when created=False."""
        comment = self.create_comment(content="Test")
        
        # Reset mock after creation
        mock_notify.reset_mock()
        
        # Update should not trigger notification
        comment.content = "Updated"
        comment.save()
        
        # Should not send notifications on update
        mock_notify.assert_not_called()
    
    @override_settings(COMMENTS={'SEND_NOTIFICATIONS': True})
    @patch('django_comments.notifications.notify_new_comment', side_effect=Exception('Email failed'))
    def test_notification_error_logged(self, mock_notify):
        """Test notification errors are logged but don't break the flow."""
        with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
            comment = self.create_comment(content="Test")
            
            # Error should be logged
            self.assertTrue(any('Failed to send notification' in log for log in logs.output))


# ============================================================================
# FLAG_COMMENT FUNCTION TESTS
# ============================================================================

class FlagCommentTests(SignalTestMixin, BaseCommentTestCase):
    """Test flag_comment helper function."""
    
    def test_flag_comment_creates_flag(self):
        """Test flag_comment creates a CommentFlag instance."""
        comment = self.create_comment(content="Test")
        
        flag = flag_comment(comment, self.regular_user, flag='spam', reason='Test spam')
        
        self.assertIsInstance(flag, CommentFlag)
        self.assertEqual(flag.user, self.regular_user)
        self.assertEqual(flag.flag, 'spam')
        self.assertEqual(flag.reason, 'Test spam')
        
        # Verify GenericForeignKey fields point to the correct comment
        # Testing underlying fields is more reliable than accessing the GFK descriptor
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(comment)
        self.assertEqual(flag.comment_type, ct)
        self.assertEqual(flag.comment_id, str(comment.pk))
        
        # Also verify we can find the flag through the reverse relationship
        self.assertIn(flag, comment.flags.all())
    
    def test_flag_comment_sends_signal(self):
        """Test flag_comment sends comment_flagged signal."""
        mock_receiver = self.create_signal_receiver(comment_flagged)
        
        comment = self.create_comment(content="Test")
        flag = flag_comment(comment, self.regular_user, flag='spam', reason='Spammy')
        
        # Verify signal was sent
        self.assertEqual(mock_receiver.call_count, 1)
        call_kwargs = mock_receiver.call_args[1]
        self.assertEqual(call_kwargs['flag'], flag)
        self.assertEqual(call_kwargs['comment'], comment)
        self.assertEqual(call_kwargs['user'], self.regular_user)
        self.assertEqual(call_kwargs['flag_type'], 'spam')
        self.assertEqual(call_kwargs['reason'], 'Spammy')
    
    def test_flag_comment_logs_moderation_action(self):
        """Test flag_comment logs a moderation action."""
        comment = self.create_comment(content="Test")
        
        flag = flag_comment(comment, self.staff_user, flag='inappropriate', reason='Bad words')
        
        # Verify moderation action was logged
        # ModerationAction uses GenericForeignKey with comment_type and comment_id
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(comment)
        
        action = ModerationAction.objects.filter(
            comment_type=ct,
            comment_id=str(comment.pk),  # Convert UUID to string
            moderator=self.staff_user,
            action='flagged'
        ).first()
        
        self.assertIsNotNone(action)
        self.assertIn('inappropriate', action.reason)
    
    def test_duplicate_flag_raises_validation_error(self):
        """Test flagging same comment twice raises ValidationError."""
        comment = self.create_comment(content="Test")
        
        # First flag succeeds
        flag1 = flag_comment(comment, self.regular_user, flag='spam')
        self.assertIsInstance(flag1, CommentFlag)
        
        # Second identical flag should raise error
        with self.assertRaises(ValidationError):
            flag_comment(comment, self.regular_user, flag='spam')
    
    def test_different_flag_types_allowed(self):
        """Test same user can flag with different flag types."""
        comment = self.create_comment(content="Test")
        
        flag1 = flag_comment(comment, self.regular_user, flag='spam')
        flag2 = flag_comment(comment, self.regular_user, flag='inappropriate')
        
        self.assertNotEqual(flag1, flag2)
        self.assertEqual(comment.flags.count(), 2)
    
    @patch('django_comments.notifications.notify_moderators_of_flag')
    def test_flag_notification_when_threshold_reached(self, mock_notify):
        """Test moderators notified when flag threshold is reached."""
        with patch.object(comments_settings, 'NOTIFY_ON_FLAG', True), \
             patch.object(comments_settings, 'FLAG_NOTIFICATION_THRESHOLD', 2):
            
            comment = self.create_comment(content="Test")
            
            # First flag - below threshold
            flag1 = flag_comment(comment, self.regular_user, flag='spam')
            # Should not trigger notification (count=1, threshold=2)
            mock_notify.assert_not_called()
            
            # Second flag - meets threshold
            other_user = User.objects.create_user(username='other', email='other@test.com')
            flag2 = flag_comment(comment, other_user, flag='spam')
            
            # Should trigger notification now (count=2, threshold=2)
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args[0]
            self.assertEqual(call_args[0], comment)
            self.assertEqual(call_args[2], 2)  # flag_count
    
    @patch('django_comments.utils.check_flag_threshold')
    def test_flag_threshold_checked(self, mock_check):
        """Test check_flag_threshold is called after flagging."""
        mock_check.return_value = {}
        
        comment = self.create_comment(content="Test")
        flag_comment(comment, self.regular_user, flag='spam')
        
        mock_check.assert_called_once_with(comment)
    
    @patch('django_comments.utils.check_auto_ban_conditions')
    @patch('django_comments.utils.auto_ban_user')
    def test_auto_ban_checked_after_flag(self, mock_auto_ban, mock_check_ban):
        """Test auto-ban conditions are checked after flagging."""
        mock_check_ban.return_value = (True, 'Multiple spam flags')
        
        comment = self.create_comment(content="Test")
        flag_comment(comment, self.regular_user, flag='spam')
        
        mock_check_ban.assert_called_once_with(comment.user)
        mock_auto_ban.assert_called_once_with(comment.user, 'Multiple spam flags')
    
    def test_flag_comment_with_unicode(self):
        """Test flag_comment handles Unicode content."""
        comment = self.create_comment(content="Test 日本語 العربية 🎉")
        
        flag = flag_comment(
            comment,
            self.regular_user,
            flag='spam',
            reason='Unicode reason 测试 مرحبا 🚀'
        )
        
        self.assertEqual(flag.reason, 'Unicode reason 测试 مرحبا 🚀')
    
    def test_flag_comment_default_flag_type(self):
        """Test flag_comment uses default flag type 'other'."""
        comment = self.create_comment(content="Test")
        
        flag = flag_comment(comment, self.regular_user)
        
        self.assertEqual(flag.flag, 'other')
    
    def test_flag_comment_empty_reason(self):
        """Test flag_comment works with empty reason."""
        comment = self.create_comment(content="Test")
        
        flag = flag_comment(comment, self.regular_user, flag='spam', reason='')
        
        self.assertEqual(flag.reason, '')


# ============================================================================
# APPROVE_COMMENT FUNCTION TESTS
# ============================================================================

class ApproveCommentTests(SignalTestMixin, BaseCommentTestCase):
    """Test approve_comment helper function."""
    
    def test_approve_comment_makes_public(self):
        """Test approve_comment makes comment public."""
        comment = self.create_comment(content="Test", is_public=False)
        
        result = approve_comment(comment, moderator=self.staff_user)
        
        comment.refresh_from_db()
        self.assertTrue(comment.is_public)
        self.assertEqual(result, comment)
    
    def test_approve_comment_sends_signal(self):
        """Test approve_comment sends comment_approved signal."""
        mock_receiver = self.create_signal_receiver(comment_approved)
        
        comment = self.create_comment(content="Test", is_public=False)
        approve_comment(comment, moderator=self.staff_user)
        
        # Verify signal was sent
        self.assertEqual(mock_receiver.call_count, 1)
        call_kwargs = mock_receiver.call_args[1]
        self.assertEqual(call_kwargs['comment'], comment)
        self.assertEqual(call_kwargs['moderator'], self.staff_user)
    
    @patch('django_comments.notifications.notify_comment_approved')
    def test_approve_sends_notification(self, mock_notify):
        """Test approve_comment sends notification to comment author."""
        with patch.object(comments_settings, 'SEND_NOTIFICATIONS', True):
            comment = self.create_comment(content="Test", is_public=False)
            approve_comment(comment, moderator=self.staff_user)
            
            mock_notify.assert_called_once_with(comment, moderator=self.staff_user)
    
    @patch('django_comments.notifications.notify_comment_approved')
    def test_approve_no_notification_when_disabled(self, mock_notify):
        """Test no notification sent when SEND_NOTIFICATIONS is False."""
        with patch.object(comments_settings, 'SEND_NOTIFICATIONS', False):
            comment = self.create_comment(content="Test", is_public=False)
            approve_comment(comment, moderator=self.staff_user)
            
            mock_notify.assert_not_called()
    
    def test_approve_already_public_no_change(self):
        """Test approving already public comment doesn't change it."""
        comment = self.create_comment(content="Test", is_public=True)
        mock_receiver = self.create_signal_receiver(comment_approved)
        
        approve_comment(comment, moderator=self.staff_user)
        
        # Should not send signal or update
        mock_receiver.assert_not_called()
    
    def test_approve_without_moderator(self):
        """Test approve_comment works without moderator parameter."""
        comment = self.create_comment(content="Test", is_public=False)
        
        result = approve_comment(comment)
        
        comment.refresh_from_db()
        self.assertTrue(comment.is_public)
    
    @patch('django_comments.notifications.notify_comment_approved', side_effect=Exception('Email error'))
    def test_approve_notification_error_logged(self, mock_notify):
        """Test notification errors are logged but don't break approval."""
        with patch.object(comments_settings, 'SEND_NOTIFICATIONS', True):
            with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
                comment = self.create_comment(content="Test", is_public=False)
                approve_comment(comment, moderator=self.staff_user)
                
                # Comment should still be approved
                comment.refresh_from_db()
                self.assertTrue(comment.is_public)
                
                # Error should be logged
                self.assertTrue(any('Failed to send approval notification' in log for log in logs.output))


# ============================================================================
# REJECT_COMMENT FUNCTION TESTS
# ============================================================================

class RejectCommentTests(SignalTestMixin, BaseCommentTestCase):
    """Test reject_comment helper function."""
    
    def test_reject_comment_makes_not_public(self):
        """Test reject_comment makes comment not public."""
        comment = self.create_comment(content="Test", is_public=True)
        
        result = reject_comment(comment, moderator=self.staff_user)
        
        comment.refresh_from_db()
        self.assertFalse(comment.is_public)
        self.assertEqual(result, comment)
    
    def test_reject_comment_sends_signal(self):
        """Test reject_comment sends comment_rejected signal."""
        mock_receiver = self.create_signal_receiver(comment_rejected)
        
        comment = self.create_comment(content="Test", is_public=True)
        reject_comment(comment, moderator=self.staff_user)
        
        # Verify signal was sent
        self.assertEqual(mock_receiver.call_count, 1)
        call_kwargs = mock_receiver.call_args[1]
        self.assertEqual(call_kwargs['comment'], comment)
        self.assertEqual(call_kwargs['moderator'], self.staff_user)
    
    @patch('django_comments.notifications.notify_comment_rejected')
    def test_reject_sends_notification(self, mock_notify):
        """Test reject_comment sends notification to comment author."""
        with patch.object(comments_settings, 'SEND_NOTIFICATIONS', True):
            comment = self.create_comment(content="Test", is_public=True)
            reject_comment(comment, moderator=self.staff_user)
            
            mock_notify.assert_called_once_with(comment, moderator=self.staff_user)
    
    @patch('django_comments.notifications.notify_comment_rejected')
    def test_reject_no_notification_when_disabled(self, mock_notify):
        """Test no notification sent when SEND_NOTIFICATIONS is False."""
        with patch.object(comments_settings, 'SEND_NOTIFICATIONS', False):
            comment = self.create_comment(content="Test", is_public=True)
            reject_comment(comment, moderator=self.staff_user)
            
            mock_notify.assert_not_called()
    
    def test_reject_already_not_public_no_change(self):
        """Test rejecting already non-public comment doesn't change it."""
        comment = self.create_comment(content="Test", is_public=False)
        mock_receiver = self.create_signal_receiver(comment_rejected)
        
        reject_comment(comment, moderator=self.staff_user)
        
        # Should not send signal or update
        mock_receiver.assert_not_called()
    
    def test_reject_without_moderator(self):
        """Test reject_comment works without moderator parameter."""
        comment = self.create_comment(content="Test", is_public=True)
        
        result = reject_comment(comment)
        
        comment.refresh_from_db()
        self.assertFalse(comment.is_public)
    
    @patch('django_comments.notifications.notify_comment_rejected', side_effect=Exception('Email error'))
    def test_reject_notification_error_logged(self, mock_notify):
        """Test notification errors are logged but don't break rejection."""
        with patch.object(comments_settings, 'SEND_NOTIFICATIONS', True):
            with self.assertLogs(comments_settings.LOGGER_NAME, level='ERROR') as logs:
                comment = self.create_comment(content="Test", is_public=True)
                reject_comment(comment, moderator=self.staff_user)
                
                # Comment should still be rejected
                comment.refresh_from_db()
                self.assertFalse(comment.is_public)
                
                # Error should be logged
                self.assertTrue(any('Failed to send rejection notification' in log for log in logs.output))


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class SignalIntegrationTests(SignalTestMixin, BaseCommentTestCase):
    """Test complete signal workflows and integration scenarios."""
    
    def test_create_comment_full_workflow(self):
        """Test complete workflow of creating a comment with all signals."""
        pre_save_receiver = self.create_signal_receiver(comment_pre_save)
        post_save_receiver = self.create_signal_receiver(comment_post_save)
        
        comment = self.create_comment(content="Integration test")
        
        # Both signals should fire
        self.assertEqual(pre_save_receiver.call_count, 1)
        self.assertEqual(post_save_receiver.call_count, 1)
        
        # Verify post_save has created=True
        post_save_kwargs = post_save_receiver.call_args[1]
        self.assertEqual(post_save_kwargs['created'], True)
    
    def test_update_comment_full_workflow(self):
        """Test complete workflow of updating a comment."""
        comment = self.create_comment(content="Original")
        
        pre_save_receiver = self.create_signal_receiver(comment_pre_save)
        post_save_receiver = self.create_signal_receiver(comment_post_save)
        
        comment.content = "Updated"
        comment.save()
        
        # Both signals should fire
        self.assertEqual(pre_save_receiver.call_count, 1)
        self.assertEqual(post_save_receiver.call_count, 1)
        
        # Verify post_save has created=False
        post_save_kwargs = post_save_receiver.call_args[1]
        self.assertEqual(post_save_kwargs['created'], False)
    
    def test_delete_comment_full_workflow(self):
        """Test complete workflow of deleting a comment."""
        comment = self.create_comment(content="To be deleted")
        
        pre_delete_receiver = self.create_signal_receiver(comment_pre_delete)
        post_delete_receiver = self.create_signal_receiver(comment_post_delete)
        
        comment.delete()
        
        # Both delete signals should fire
        self.assertEqual(pre_delete_receiver.call_count, 1)
        self.assertEqual(post_delete_receiver.call_count, 1)
    
    def test_flag_approve_workflow(self):
        """Test workflow: flag comment, then approve it."""
        comment = self.create_comment(content="Test", is_public=False)
        
        flagged_receiver = self.create_signal_receiver(comment_flagged)
        approved_receiver = self.create_signal_receiver(comment_approved)
        
        # Flag it
        flag = flag_comment(comment, self.regular_user, flag='spam')
        self.assertEqual(flagged_receiver.call_count, 1)
        
        # Approve it
        approve_comment(comment, moderator=self.staff_user)
        self.assertEqual(approved_receiver.call_count, 1)
        
        comment.refresh_from_db()
        self.assertTrue(comment.is_public)
    
    def test_flag_reject_workflow(self):
        """Test workflow: flag comment, then reject it."""
        comment = self.create_comment(content="Test", is_public=True)
        
        flagged_receiver = self.create_signal_receiver(comment_flagged)
        rejected_receiver = self.create_signal_receiver(comment_rejected)
        
        # Flag it
        flag = flag_comment(comment, self.regular_user, flag='inappropriate')
        self.assertEqual(flagged_receiver.call_count, 1)
        
        # Reject it
        reject_comment(comment, moderator=self.staff_user)
        self.assertEqual(rejected_receiver.call_count, 1)
        
        comment.refresh_from_db()
        self.assertFalse(comment.is_public)
    
    @override_settings(COMMENTS={
        'SEND_NOTIFICATIONS': True,
        'MODERATOR_REQUIRED': True
    })
    @patch('django_comments.notifications.notify_new_comment')
    @patch('django_comments.notifications.notify_moderators')
    def test_moderation_required_workflow(self, mock_notify_mods, mock_notify_new):
        """Test workflow when moderation is required."""
        comment = self.create_comment(content="Needs moderation", is_public=False)
        
        # Should notify moderators and content owner
        mock_notify_new.assert_called_once_with(comment)
        mock_notify_mods.assert_called_once_with(comment)
    
    @override_settings(COMMENTS={'SEND_NOTIFICATIONS': True})
    @patch('django_comments.notifications.notify_comment_reply')
    def test_reply_notification_workflow(self, mock_notify_reply):
        """Test notification workflow for reply comments."""
        parent = self.create_comment(content="Parent")
        reply = self.create_comment(content="Reply", parent=parent)
        
        # Should trigger reply notification
        mock_notify_reply.assert_called_once_with(reply, parent_comment=parent)
    
    @patch('django_comments.utils.apply_automatic_flags')
    def test_automatic_flags_on_create_only(self, mock_apply):
        """Test automatic flags only applied on creation, not updates."""
        comment = self.create_comment(content="Test")
        self.assertEqual(mock_apply.call_count, 1)
        
        mock_apply.reset_mock()
        
        # Update should not trigger automatic flags
        comment.content = "Updated"
        comment.save()
        
        mock_apply.assert_not_called()


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class SignalEdgeCaseTests(SignalTestMixin, BaseCommentTestCase):
    """Test edge cases and error handling in signals."""
    
    def test_signal_with_none_comment(self):
        """Test signals handle None comment gracefully."""
        # This is more of a defensive test
        try:
            safe_send(comment_pre_save, sender=self.Comment, comment=None)
        except Exception as e:
            self.fail(f"Signal with None comment raised exception: {e}")
    
    def test_multiple_receivers_on_same_signal(self):
        """Test multiple receivers can listen to same signal."""
        receiver1 = self.create_signal_receiver(comment_flagged)
        receiver2 = self.create_signal_receiver(comment_flagged)
        receiver3 = self.create_signal_receiver(comment_flagged)
        
        comment = self.create_comment(content="Test")
        flag_comment(comment, self.regular_user, flag='spam')
        
        # All receivers should be called
        self.assertEqual(receiver1.call_count, 1)
        self.assertEqual(receiver2.call_count, 1)
        self.assertEqual(receiver3.call_count, 1)
    
    def test_signal_with_unicode_content(self):
        """Test signals work with Unicode content."""
        comment = self.create_comment(content="Unicode test 日本語 العربية 🎉")
        
        flagged_receiver = self.create_signal_receiver(comment_flagged)
        flag = flag_comment(comment, self.regular_user, flag='spam', reason='Unicode 测试')
        
        # Should work without issues
        self.assertEqual(flagged_receiver.call_count, 1)
    
    def test_signal_with_very_long_reason(self):
        """Test signals handle very long flag reasons."""
        comment = self.create_comment(content="Test")
        long_reason = "x" * 1000
        
        flag = flag_comment(comment, self.regular_user, flag='spam', reason=long_reason)
        
        self.assertEqual(flag.reason, long_reason)
    
    def test_approve_reject_same_comment_multiple_times(self):
        """Test approving and rejecting same comment multiple times."""
        comment = self.create_comment(content="Test", is_public=False)
        
        approved_receiver = self.create_signal_receiver(comment_approved)
        rejected_receiver = self.create_signal_receiver(comment_rejected)
        
        # Approve
        approve_comment(comment, moderator=self.staff_user)
        self.assertEqual(approved_receiver.call_count, 1)
        
        # Reject
        reject_comment(comment, moderator=self.staff_user)
        self.assertEqual(rejected_receiver.call_count, 1)
        
        # Approve again
        approve_comment(comment, moderator=self.staff_user)
        self.assertEqual(approved_receiver.call_count, 2)
        
        # Try to approve again (already public)
        approve_comment(comment, moderator=self.staff_user)
        self.assertEqual(approved_receiver.call_count, 2)  # Should not increment
    
    def test_flag_comment_after_deletion(self):
        """Test that comment flags are deleted along with comment."""
        comment = self.create_comment(content="Test")
        flag = flag_comment(comment, self.regular_user, flag='spam')
        flag_id = flag.pk
        
        # Delete the comment
        comment.delete()
        
        # Flag should also be deleted (cascade delete)
        self.assertFalse(CommentFlag.objects.filter(pk=flag_id).exists())
    
    @patch('django_comments.notifications.notify_new_comment')
    @patch('django_comments.notifications.notify_comment_reply')
    def test_orphaned_reply_notifications(self, mock_reply, mock_new):
        """Test reply notifications when parent is missing."""
        with patch.object(comments_settings, 'SEND_NOTIFICATIONS', True):
            # Create comment without parent (orphaned)
            comment = self.create_comment(content="Orphaned reply")
            
            # Should call new comment but not reply (no parent)
            mock_new.assert_called_once()
            mock_reply.assert_not_called()
    
    def test_concurrent_flags_same_comment(self):
        """Test multiple users flagging same comment concurrently."""
        comment = self.create_comment(content="Test")
        
        users = [
            User.objects.create_user(username=f'user{i}', email=f'user{i}@test.com')
            for i in range(5)
        ]
        
        # All users flag the comment
        flags = []
        for user in users:
            flag = flag_comment(comment, user, flag='spam')
            flags.append(flag)
        
        # Should have 5 different flags
        self.assertEqual(comment.flags.count(), 5)
        self.assertEqual(len(set(flags)), 5)
    
    def test_signal_receiver_exception_handling(self):
        """Test that exceptions in signal receivers are propagated by Django signals."""
        def bad_receiver(sender, **kwargs):
            raise Exception("Receiver error")
        
        comment_flagged.connect(bad_receiver)
        self.signal_receivers.append((comment_flagged, bad_receiver))
        
        comment = self.create_comment(content="Test")
        
        # Django signals propagate exceptions by default
        with self.assertRaises(Exception) as cm:
            flag = flag_comment(comment, self.regular_user, flag='spam')
        
        self.assertIn("Receiver error", str(cm.exception))
    
    def test_empty_string_reason(self):
        """Test flagging with empty string reason."""
        comment = self.create_comment(content="Test")
        
        flag = flag_comment(comment, self.regular_user, flag='spam', reason='')
        
        self.assertEqual(flag.reason, '')
    
    def test_whitespace_only_reason(self):
        """Test flagging with whitespace-only reason."""
        comment = self.create_comment(content="Test")
        
        flag = flag_comment(comment, self.regular_user, flag='spam', reason='   ')
        
        self.assertEqual(flag.reason, '   ')
    
    def test_special_characters_in_flag_reason(self):
        """Test flag reasons with special characters."""
        comment = self.create_comment(content="Test")
        
        special_reason = "Test <script>alert('xss')</script> & \"quotes\" 'apostrophes'"
        flag = flag_comment(comment, self.regular_user, flag='spam', reason=special_reason)
        
        self.assertEqual(flag.reason, special_reason)


# ============================================================================
# PERFORMANCE AND OPTIMIZATION TESTS
# ============================================================================

class SignalPerformanceTests(SignalTestMixin, BaseCommentTestCase):
    """Test signal performance and optimization."""
    
    def test_signals_dont_cause_extra_queries(self):
        """Test signals don't cause N+1 queries."""
        from django.test.utils import override_settings
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        
        with CaptureQueriesContext(connection) as context:
            comment = self.create_comment(content="Performance test")
            query_count_create = len(context.captured_queries)
        
        # Creating another comment should have similar query count
        with CaptureQueriesContext(connection) as context:
            comment2 = self.create_comment(content="Performance test 2")
            query_count_create2 = len(context.captured_queries)
        
        # Query counts should be consistent (allowing reasonable variance)
        # Signals may add a few queries but shouldn't cause N+1 problems
        self.assertAlmostEqual(query_count_create, query_count_create2, delta=5)
    
    @patch('django_comments.utils.apply_automatic_flags')
    @patch('django_comments.signals.trigger_notifications')
    def test_bulk_create_performance(self, mock_notify, mock_flags):
        """Test performance with bulk operations."""
        # This test ensures signals are optimized for bulk operations
        comments = [
            self.Comment(
                content=f"Bulk comment {i}",
                content_type=self.content_type,
                object_id=self.test_obj.pk,
                user=self.regular_user,
                is_public=True
            )
            for i in range(10)
        ]
        
        # Note: bulk_create doesn't trigger signals
        created = self.Comment.objects.bulk_create(comments)
        
        # Signals should not be called with bulk_create
        mock_flags.assert_not_called()
        mock_notify.assert_not_called()