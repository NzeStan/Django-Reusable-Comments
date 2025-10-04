"""
Tests for the django_comments admin interface.
"""
import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from ..admin import CommentAdmin, CommentFlagAdmin
from ..models import Comment, CommentFlag


User = get_user_model()


class MockRequest:
    """Mock request for admin testing."""
    def __init__(self, user=None):
        self.user = user


class MockSuperUser:
    """Mock superuser for admin testing."""
    is_staff = True
    is_superuser = True
    
    def has_perm(self, perm):
        return True


@pytest.mark.django_db
class TestCommentAdmin:
    """Tests for the CommentAdmin class."""
    
    def setup_method(self):
        """Set up for each test."""
        self.admin_site = AdminSite()
        self.comment_admin = CommentAdmin(Comment, self.admin_site)
        self.factory = RequestFactory()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password'
        )
    
    def test_content_snippet(self, comment):
        """Test content_snippet method."""
        # Short content
        comment.content = "Short content"
        snippet = self.comment_admin.content_snippet(comment)
        assert snippet == "Short content"
        
        # Long content
        comment.content = "This is a very long comment that should be truncated in the admin interface display."
        snippet = self.comment_admin.content_snippet(comment)
        assert snippet == "This is a very long comment that should be truncat..."
        assert len(snippet) <= 53  # 50 chars plus ellipsis
    
    def test_user_info(self, comment, user):
        """Test user_info method."""
        # With user
        info = self.comment_admin.user_info(comment)
        assert user.get_username() in info
        
        # Without user
        comment.user = None
        comment.user_name = "Anonymous Person"
        info = self.comment_admin.user_info(comment)
        assert info == "Anonymous Person"
    
    def test_approve_comments_action(self, comment):
        """Test approve_comments admin action."""
        # Make comment non-public first
        comment.is_public = False
        comment.save()

        # Create a real HttpRequest object
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.superuser

        # Attach a messages framework storage backend to the request
        setattr(request, 'session', {})  # Fake session dict
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)

        # Execute the action
        self.comment_admin.approve_comments(request, Comment.objects.filter(pk=comment.pk))

        # Check that the comment is now public
        comment.refresh_from_db()
        assert comment.is_public is True
    
    def test_reject_comments_action(self, comment):
        """Test reject_comments admin action."""
        # Create a real request
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.superuser

        # Attach messages backend
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)

        # Execute the action
        self.comment_admin.reject_comments(request, Comment.objects.filter(pk=comment.pk))

        # Check that the comment is now non-public
        comment.refresh_from_db()
        assert comment.is_public is False

    def test_mark_as_removed_action(self, comment):
        """Test mark_as_removed admin action."""
        # Create a real request
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.superuser

        # Attach messages backend
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)

        # Execute the action
        self.comment_admin.mark_as_removed(request, Comment.objects.filter(pk=comment.pk))

        # Check that the comment is now marked as removed
        comment.refresh_from_db()
        assert comment.is_removed is True


@pytest.mark.django_db
class TestCommentFlagAdmin:
    """Tests for the CommentFlagAdmin class."""
    
    def setup_method(self):
        """Set up for each test."""
        self.admin_site = AdminSite()
        self.flag_admin = CommentFlagAdmin(CommentFlag, self.admin_site)
    
    def test_comment_snippet(self, flagged_comment):
        """Test comment_snippet method."""
        flag = flagged_comment.flags.first()
        
        # Short content
        flagged_comment.content = "Short content"
        flagged_comment.save()
        snippet = self.flag_admin.comment_snippet(flag)
        assert snippet == "Short content"
        
        # Long content
        flagged_comment.content = "This is a very long comment that should be truncated in the admin interface display."
        flagged_comment.save()
        snippet = self.flag_admin.comment_snippet(flag)
        assert snippet == "This is a very long comment that should be truncat..."
        assert len(snippet) <= 53  # 50 chars plus ellipsis


@pytest.mark.django_db
class TestAdminViews:
    """Tests for the admin views."""
    
    @pytest.fixture
    def admin_client(self, client):
        """Create an admin client."""
        User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password'
        )
        client.login(username='admin', password='password')
        return client
    
    def test_comment_admin_list_view(self, admin_client, comment):
        """Test the comment admin list view."""
        url = reverse('admin:django_comments_comment_changelist')
        response = admin_client.get(url)

        assert response.status_code == 200

        # Compute expected snippet
        if len(comment.content) > 50:
            expected_snippet = f"{comment.content[:50]}..."
        else:
            expected_snippet = comment.content

        assert expected_snippet in response.content.decode()

    
    def test_comment_admin_detail_view(self, admin_client, comment):
        """Test the comment admin detail view."""
        url = reverse('admin:django_comments_comment_change', args=[comment.pk])
        response = admin_client.get(url)
        
        assert response.status_code == 200
        assert comment.content in str(response.content)
    
    def test_comment_flag_admin_list_view(self, admin_client, flagged_comment):
        """Test the comment flag admin list view."""
        flag = flagged_comment.flags.first()
        url = reverse('admin:django_comments_commentflag_changelist')
        response = admin_client.get(url)
        
        assert response.status_code == 200
        assert flag.get_flag_display() in str(response.content)
    
    def test_comment_flag_admin_detail_view(self, admin_client, flagged_comment):
        """Test the comment flag admin detail view."""
        flag = flagged_comment.flags.first()
        url = reverse('admin:django_comments_commentflag_change', args=[flag.pk])
        response = admin_client.get(url)
        
        assert response.status_code == 200
        assert flag.reason in str(response.content)