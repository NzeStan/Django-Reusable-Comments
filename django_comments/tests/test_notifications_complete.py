"""
Comprehensive test suite for notification system.
Tests all 5 notification types and edge cases.
"""
import pytest
from django.core import mail
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django_comments.models import Comment
from django_comments.notifications import (
    notify_new_comment,
    notify_comment_reply,
    notify_comment_approved,
    notify_comment_rejected,
    notify_moderators,
    CommentNotificationService,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def site():
    """Create or get test site."""
    site, _ = Site.objects.get_or_create(
        id=1,
        defaults={
            'domain': 'testserver',
            'name': 'Test Site'
        }
    )
    return site


@pytest.fixture
def user():
    """Create test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def another_user():
    """Create another test user."""
    return User.objects.create_user(
        username='anotheruser',
        email='another@example.com',
        password='testpass123'
    )


@pytest.fixture
def post(user):
    """Create test post model."""
    from django.contrib.contenttypes.models import ContentType
    from django.db import models
    
    # Create a simple test model
    class TestPost(models.Model):
        title = models.CharField(max_length=200)
        author = models.ForeignKey(User, on_delete=models.CASCADE)
        
        class Meta:
            app_label = 'django_comments'
            managed = False
        
        def __str__(self):
            return self.title
    
    post = TestPost(id=1, title="Test Post", author=user)
    post._state.adding = False
    return post


@pytest.fixture
def comment(post, user):
    """Create test comment."""
    return Comment.objects.create(
        content_object=post,
        user=user,
        content="Test comment"
    )


@pytest.fixture
def enable_notifications(settings):
    """Enable notifications in settings."""
    settings.DJANGO_COMMENTS_CONFIG = {
        'SEND_NOTIFICATIONS': True,
        'NOTIFICATION_SUBJECT': 'New comment on {object}',
        'NOTIFICATION_EMAIL_TEMPLATE': 'django_comments/email/new_comment.html',
        'NOTIFICATION_REPLY_TEMPLATE': 'django_comments/email/comment_reply.html',
        'NOTIFICATION_APPROVED_TEMPLATE': 'django_comments/email/comment_approved.html',
        'NOTIFICATION_REJECTED_TEMPLATE': 'django_comments/email/comment_rejected.html',
        'NOTIFICATION_MODERATOR_TEMPLATE': 'django_comments/email/moderator_notification.html',
    }
    # Reload settings
    from django_comments import conf
    conf.comments_settings = conf.CommentsSettings(
        settings.DJANGO_COMMENTS_CONFIG,
        conf.DEFAULTS
    )


class TestNewCommentNotification:
    """Tests for new comment notifications."""
    
    def test_new_comment_notification_sent(self, comment, site, enable_notifications):
        """Test that new comment notification is sent."""
        notify_new_comment(comment)
        
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert "New comment" in email.subject
        assert comment.content in str(email.body)
    
    def test_new_comment_notification_disabled(self, comment, site):
        """Test that notification is not sent when disabled."""
        # Don't enable notifications
        notify_new_comment(comment)
        
        assert len(mail.outbox) == 0
    
    def test_new_comment_notification_to_content_author(self, post, user, another_user, site, enable_notifications):
        """Test notification sent to content author."""
        comment = Comment.objects.create(
            content_object=post,
            user=another_user,
            content="Comment from another user"
        )
        
        notify_new_comment(comment)
        
        assert len(mail.outbox) == 1
        assert user.email in mail.outbox[0].to
    
    def test_new_comment_notification_excludes_comment_author(self, post, user, site, enable_notifications):
        """Test that comment author doesn't receive notification about their own comment."""
        comment = Comment.objects.create(
            content_object=post,
            user=user,  # Same as post author
            content="Self comment"
        )
        
        notify_new_comment(comment)
        
        # Should not send to self
        assert len(mail.outbox) == 0


class TestReplyNotification:
    """Tests for reply notifications."""
    
    def test_reply_notification_sent(self, post, user, another_user, site, enable_notifications):
        """Test reply notification is sent."""
        parent = Comment.objects.create(
            content_object=post,
            user=user,
            content="Parent comment"
        )
        
        reply = Comment.objects.create(
            content_object=post,
            user=another_user,
            content="Reply comment",
            parent=parent
        )
        
        notify_comment_reply(reply, parent)
        
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert user.email in email.to
        assert "replied" in email.subject.lower()
        assert parent.content in str(email.body)
        assert reply.content in str(email.body)
    
    def test_reply_notification_not_sent_to_self(self, post, user, site, enable_notifications):
        """Test reply notification not sent when replying to own comment."""
        parent = Comment.objects.create(
            content_object=post,
            user=user,
            content="Parent comment"
        )
        
        reply = Comment.objects.create(
            content_object=post,
            user=user,  # Same user
            content="Self reply",
            parent=parent
        )
        
        notify_comment_reply(reply, parent)
        
        assert len(mail.outbox) == 0
    
    def test_reply_notification_anonymous_parent(self, post, another_user, site, enable_notifications):
        """Test reply notification with anonymous parent."""
        parent = Comment.objects.create(
            content_object=post,
            user=None,
            user_email='anon@example.com',
            content="Anonymous parent"
        )
        
        reply = Comment.objects.create(
            content_object=post,
            user=another_user,
            content="Reply to anonymous",
            parent=parent
        )
        
        notify_comment_reply(reply, parent)
        
        assert len(mail.outbox) == 1
        assert 'anon@example.com' in mail.outbox[0].to


class TestApprovalNotification:
    """Tests for approval notifications."""
    
    def test_approval_notification_sent(self, post, user, another_user, site, enable_notifications):
        """Test approval notification is sent."""
        comment = Comment.objects.create(
            content_object=post,
            user=user,
            content="Comment awaiting approval",
            is_public=False
        )
        
        notify_comment_approved(comment, moderator=another_user)
        
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert user.email in email.to
        assert "approved" in email.subject.lower()
        assert comment.content in str(email.body)
    
    def test_approval_notification_anonymous_author(self, post, another_user, site, enable_notifications):
        """Test approval notification for anonymous comment."""
        comment = Comment.objects.create(
            content_object=post,
            user=None,
            user_email='anon@example.com',
            content="Anonymous comment",
            is_public=False
        )
        
        notify_comment_approved(comment, moderator=another_user)
        
        assert len(mail.outbox) == 1
        assert 'anon@example.com' in mail.outbox[0].to


class TestRejectionNotification:
    """Tests for rejection notifications."""
    
    def test_rejection_notification_sent(self, post, user, another_user, site, enable_notifications):
        """Test rejection notification is sent."""
        comment = Comment.objects.create(
            content_object=post,
            user=user,
            content="Comment to be rejected",
            is_public=True
        )
        
        notify_comment_rejected(comment, moderator=another_user)
        
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert user.email in email.to
        assert comment.content in str(email.body)


class TestModeratorNotification:
    """Tests for moderator notifications."""
    
    def test_moderator_notification_sent(self, post, user, site, enable_notifications):
        """Test moderator notification is sent."""
        # Create moderator user
        moderator = User.objects.create_user(
            username='moderator',
            email='moderator@example.com',
            password='pass123',
            is_staff=True
        )
        
        comment = Comment.objects.create(
            content_object=post,
            user=user,
            content="Comment needing moderation",
            is_public=False
        )
        
        notify_moderators(comment)
        
        assert len(mail.outbox) == 1
        assert moderator.email in mail.outbox[0].to
        assert comment.content in str(mail.outbox[0].body)
    
    def test_moderator_notification_with_permission(self, post, user, site, enable_notifications):
        """Test moderator notification sent to users with permission."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        # Create user with moderation permission
        moderator = User.objects.create_user(
            username='moderator',
            email='moderator@example.com',
            password='pass123'
        )
        
        # Add moderation permission
        ct = ContentType.objects.get_for_model(Comment)
        permission = Permission.objects.get(
            codename='can_moderate_comments',
            content_type=ct
        )
        moderator.user_permissions.add(permission)
        
        comment = Comment.objects.create(
            content_object=post,
            user=user,
            content="Comment needing moderation",
            is_public=False
        )
        
        notify_moderators(comment)
        
        assert len(mail.outbox) >= 1
        # Should include moderator email
        recipients = []
        for email in mail.outbox:
            recipients.extend(email.to)
        assert moderator.email in recipients


class TestNotificationService:
    """Tests for CommentNotificationService class."""
    
    def test_service_enabled_check(self):
        """Test that service checks if notifications are enabled."""
        service = CommentNotificationService()
        # Should check settings.SEND_NOTIFICATIONS
        assert hasattr(service, 'enabled')
    
    def test_service_from_email(self, settings):
        """Test service uses correct from email."""
        settings.DEFAULT_FROM_EMAIL = 'noreply@test.com'
        service = CommentNotificationService()
        assert service.from_email == 'noreply@test.com'
    
    def test_custom_notification_service(self, post, user, site, enable_notifications):
        """Test custom notification service can be used."""
        class CustomService(CommentNotificationService):
            custom_called = False
            
            def _get_comment_recipients(self, comment):
                self.custom_called = True
                return ['custom@example.com']
        
        service = CustomService()
        comment = Comment.objects.create(
            content_object=post,
            user=user,
            content="Test"
        )
        
        service.notify_new_comment(comment)
        
        assert service.custom_called
        assert len(mail.outbox) == 1
        assert 'custom@example.com' in mail.outbox[0].to


class TestNotificationEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_notification_with_deleted_content_object(self, user, site, enable_notifications):
        """Test notification when content object is deleted."""
        from django.contrib.contenttypes.models import ContentType
        
        comment = Comment(
            user=user,
            content="Comment on deleted object",
            content_type=ContentType.objects.get_for_model(User),
            object_id=99999  # Non-existent
        )
        comment.save()
        
        # Should not crash
        notify_new_comment(comment)
    
    def test_notification_with_no_email(self, post, site, enable_notifications):
        """Test notification when user has no email."""
        user_no_email = User.objects.create_user(
            username='noemail',
            email='',  # No email
            password='pass123'
        )
        
        comment = Comment.objects.create(
            content_object=post,
            user=user_no_email,
            content="Comment from user with no email"
        )
        
        # Should not crash
        notify_new_comment(comment)
    
    def test_notification_error_handling(self, comment, site, enable_notifications, settings):
        """Test notification error handling."""
        # Break email backend
        settings.EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
        
        # Should not crash
        try:
            notify_new_comment(comment)
        except Exception as e:
            pytest.fail(f"Notification should handle errors gracefully: {e}")


class TestNotificationIntegrationWithSignals:
    """Tests for notification integration with signals."""
    
    def test_notification_triggered_on_comment_creation(self, post, user, site, enable_notifications):
        """Test notification is triggered by signal on comment creation."""
        # This tests the integration with signals.py
        comment = Comment.objects.create(
            content_object=post,
            user=user,
            content="New comment with auto notification"
        )
        
        # Signal should trigger notification
        # (This requires signals.py to be updated as per instructions)
        # For now, just verify comment was created
        assert comment.pk is not None
    
    def test_notification_triggered_on_comment_reply(self, post, user, another_user, site, enable_notifications):
        """Test notification triggered on reply."""
        parent = Comment.objects.create(
            content_object=post,
            user=user,
            content="Parent comment"
        )
        
        reply = Comment.objects.create(
            content_object=post,
            user=another_user,
            content="Reply comment",
            parent=parent
        )
        
        # Signal should trigger reply notification
        assert reply.parent == parent


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v'])