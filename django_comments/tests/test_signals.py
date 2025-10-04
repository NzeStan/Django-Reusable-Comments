"""
Tests for the django_comments signals.
"""
import pytest
from django.dispatch import receiver

from ..models import Comment
from ..signals import (
    comment_pre_save, comment_post_save, 
    comment_pre_delete, comment_post_delete,
    comment_flagged, comment_approved, comment_rejected,
    approve_comment, reject_comment, flag_comment
)


@pytest.mark.django_db
class TestCommentLifecycleSignals:
    """Tests for the comment lifecycle signals."""
    
    def test_comment_pre_save_signal(self, comment, user):
        """Test that the comment_pre_save signal is sent."""
        # Set up signal receiver
        signal_received = False
        
        @receiver(comment_pre_save)
        def on_comment_pre_save(sender, comment, **kwargs):
            nonlocal signal_received
            signal_received = True
            
        # Update the comment to trigger the signal
        comment.content = "Updated content to trigger pre_save"
        comment.save()
        
        assert signal_received
        
    def test_comment_post_save_signal(self, comment, user):
        """Test that the comment_post_save signal is sent."""
        # Set up signal receiver
        signal_received = False
        created_status = None
        
        @receiver(comment_post_save)
        def on_comment_post_save(sender, comment, created, **kwargs):
            nonlocal signal_received, created_status
            signal_received = True
            created_status = created
            
        # Update the comment to trigger the signal
        comment.content = "Updated content to trigger post_save"
        comment.save()
        
        assert signal_received
        assert created_status is False  # Not a new comment
        
        # Create a new comment to test 'created' status
        signal_received = False
        created_status = None
        
        Comment.objects.create(
            content_type=comment.content_type,
            object_id=comment.object_id,
            user=user,
            content="New comment to test created status"
        )
        
        assert signal_received
        assert created_status is True  # New comment
        
    def test_comment_delete_signals(self, comment):
        """Test that the comment delete signals are sent."""
        # Set up signal receivers
        pre_delete_received = False
        post_delete_received = False
        
        @receiver(comment_pre_delete)
        def on_comment_pre_delete(sender, comment, **kwargs):
            nonlocal pre_delete_received
            pre_delete_received = True
            
        @receiver(comment_post_delete)
        def on_comment_post_delete(sender, comment, **kwargs):
            nonlocal post_delete_received
            post_delete_received = True
            
        # Delete the comment to trigger the signals
        comment.delete()
        
        assert pre_delete_received
        assert post_delete_received


@pytest.mark.django_db
class TestCommentModerationSignals:
    """Tests for the comment moderation signals."""
    
    def test_flag_comment_signal(self, comment, user):
        """Test that the comment_flagged signal is sent."""
        # Set up signal receiver
        signal_received = False
        flag_info = {}
        
        @receiver(comment_flagged)
        def on_comment_flagged(sender, flag, comment, user, flag_type, reason, **kwargs):
            nonlocal signal_received, flag_info
            signal_received = True
            flag_info = {
                'comment': comment,
                'user': user,
                'flag_type': flag_type,
                'reason': reason
            }
            
        # Flag the comment to trigger the signal
        flag_comment(
            comment=comment,
            user=user,
            flag='spam',
            reason='Test flagging'
        )
        
        assert signal_received
        assert flag_info['comment'] == comment
        assert flag_info['user'] == user
        assert flag_info['flag_type'] == 'spam'
        assert flag_info['reason'] == 'Test flagging'
        
    def test_approve_comment_signal(self, comment):
        """Test that the comment_approved signal is sent."""
        # First make the comment non-public
        comment.is_public = False
        comment.save()
        
        # Set up signal receiver
        signal_received = False
        signal_comment = None
        signal_moderator = None
        
        @receiver(comment_approved)
        def on_comment_approved(sender, comment, moderator, **kwargs):
            nonlocal signal_received, signal_comment, signal_moderator
            signal_received = True
            signal_comment = comment
            signal_moderator = moderator
            
        # Approve the comment to trigger the signal
        approve_comment(comment, moderator="test_moderator")
        
        assert signal_received
        assert signal_comment == comment
        assert signal_moderator == "test_moderator"
        assert comment.is_public is True
        
    def test_reject_comment_signal(self, comment):
        """Test that the comment_rejected signal is sent."""
        # Set up signal receiver
        signal_received = False
        signal_comment = None
        signal_moderator = None
        
        @receiver(comment_rejected)
        def on_comment_rejected(sender, comment, moderator, **kwargs):
            nonlocal signal_received, signal_comment, signal_moderator
            signal_received = True
            signal_comment = comment
            signal_moderator = moderator
            
        # Reject the comment to trigger the signal
        reject_comment(comment, moderator="test_moderator")
        
        assert signal_received
        assert signal_comment == comment
        assert signal_moderator == "test_moderator"
        assert comment.is_public is False


@pytest.mark.django_db
class TestCustomSignalHandlers:
    """Tests for custom signal handlers."""
    
    def test_custom_post_save_handler(self, comment, user):
        """Test that a custom comment_post_save handler works."""
        # Create a tracker to record signal activity
        class SignalTracker:
            def __init__(self):
                self.signals_received = []
                
            def on_comment_post_save(self, sender, comment, created, **kwargs):
                self.signals_received.append({
                    'comment_id': comment.pk,
                    'created': created,
                    'content': comment.content
                })
        
        # Create tracker and connect to signal
        tracker = SignalTracker()
        comment_post_save.connect(tracker.on_comment_post_save)
        
        # Update the comment to trigger the signal
        comment.content = "Updated content for custom handler test"
        comment.save()
        
        # Check that the signal was received
        assert len(tracker.signals_received) == 1
        assert tracker.signals_received[0]['comment_id'] == comment.pk
        assert tracker.signals_received[0]['created'] is False
        assert tracker.signals_received[0]['content'] == "Updated content for custom handler test"
        
        # Disconnect the signal to clean up
        comment_post_save.disconnect(tracker.on_comment_post_save)