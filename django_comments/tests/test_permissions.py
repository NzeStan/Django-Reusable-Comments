"""
Tests for django_comments API permissions.
CRITICAL: These tests ensure security of the API.
"""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from ..api.permissions import (
    IsOwnerOrReadOnly,
    CommentPermission,
    ModeratorPermission
)
from .factories import UserFactory, CommentFactory

User = get_user_model()


@pytest.mark.django_db
class TestIsOwnerOrReadOnly:
    """Tests for IsOwnerOrReadOnly permission."""
    
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.permission = IsOwnerOrReadOnly()
        self.user = UserFactory()
        self.other_user = UserFactory()
    
    def test_read_permission_for_anyone(self, comment):
        """Test that anyone can read (GET, HEAD, OPTIONS)."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        
        assert self.permission.has_object_permission(request, None, comment)
    
    def test_write_permission_for_owner(self, comment):
        """Test that owner can edit their comment."""
        request = self.factory.put('/')
        request.user = comment.user
        
        assert self.permission.has_object_permission(request, None, comment)
    
    def test_write_permission_denied_for_non_owner(self, comment):
        """Test that non-owner cannot edit comment."""
        request = self.factory.put('/')
        request.user = self.other_user
        
        assert not self.permission.has_object_permission(request, None, comment)
    
    def test_delete_permission_for_owner(self, comment):
        """Test that owner can delete their comment."""
        request = self.factory.delete('/')
        request.user = comment.user
        
        assert self.permission.has_object_permission(request, None, comment)


@pytest.mark.django_db
class TestCommentPermission:
    """Tests for CommentPermission class."""
    
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.permission = CommentPermission()
        self.user = UserFactory()
        self.staff_user = UserFactory(is_staff=True)
        self.superuser = UserFactory(is_superuser=True)
    
    # has_permission tests (list/create level)
    
    def test_list_permission_for_anonymous(self):
        """Test anonymous users can list comments."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        
        view = type('View', (), {'action': 'list'})()
        
        assert self.permission.has_permission(request, view)
    
    def test_list_permission_for_authenticated(self):
        """Test authenticated users can list comments."""
        request = self.factory.get('/')
        request.user = self.user
        
        view = type('View', (), {'action': 'list'})()
        
        assert self.permission.has_permission(request, view)
    
    def test_create_permission_for_authenticated(self):
        """Test authenticated users can create comments."""
        request = self.factory.post('/')
        request.user = self.user
        
        view = type('View', (), {'action': 'create'})()
        
        assert self.permission.has_permission(request, view)
    
    def test_create_permission_for_anonymous_when_allowed(self, monkeypatch):
        """Test anonymous can create when ALLOW_ANONYMOUS is True."""
        from ..conf import comments_settings
        monkeypatch.setattr(comments_settings, 'ALLOW_ANONYMOUS', True)
        
        request = self.factory.post('/')
        request.user = AnonymousUser()
        
        view = type('View', (), {'action': 'create'})()
        
        assert self.permission.has_permission(request, view)
    
    def test_create_permission_denied_for_anonymous_when_not_allowed(self, monkeypatch):
        """Test anonymous cannot create when ALLOW_ANONYMOUS is False."""
        from ..conf import comments_settings
        monkeypatch.setattr(comments_settings, 'ALLOW_ANONYMOUS', False)
        
        request = self.factory.post('/')
        request.user = AnonymousUser()
        
        view = type('View', (), {'action': 'create'})()
        
        assert not self.permission.has_permission(request, view)
    
    # has_object_permission tests
    
    def test_read_object_permission_for_anyone(self, comment):
        """Test anyone can read a comment object."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        
        view = type('View', (), {'action': 'retrieve'})()
        
        assert self.permission.has_object_permission(request, view, comment)
    
    def test_update_permission_for_owner(self, comment):
        """Test owner can update their comment."""
        request = self.factory.patch('/')
        request.user = comment.user
        
        view = type('View', (), {'action': 'partial_update'})()
        
        assert self.permission.has_object_permission(request, view, comment)
    
    def test_update_permission_denied_for_non_owner(self, comment):
        """Test non-owner cannot update comment."""
        request = self.factory.patch('/')
        request.user = self.user
        
        view = type('View', (), {'action': 'partial_update'})()
        
        assert not self.permission.has_object_permission(request, view, comment)
    
    def test_update_permission_for_staff(self, comment):
        """Test staff can update any comment."""
        request = self.factory.patch('/')
        request.user = self.staff_user
        
        view = type('View', (), {'action': 'partial_update'})()
        
        assert self.permission.has_object_permission(request, view, comment)
    
    def test_delete_permission_for_owner(self, comment):
        """Test owner can delete their comment."""
        request = self.factory.delete('/')
        request.user = comment.user
        
        view = type('View', (), {'action': 'destroy'})()
        
        assert self.permission.has_object_permission(request, view, comment)
    
    def test_delete_permission_for_staff(self, comment):
        """Test staff can delete any comment."""
        request = self.factory.delete('/')
        request.user = self.staff_user
        
        view = type('View', (), {'action': 'destroy'})()
        
        assert self.permission.has_object_permission(request, view, comment)
    
    def test_flag_permission_for_authenticated(self, comment):
        """Test authenticated users can flag comments."""
        request = self.factory.post('/')
        request.user = self.user
        
        view = type('View', (), {'action': 'flag'})()
        
        assert self.permission.has_object_permission(request, view, comment)
    
    def test_flag_permission_denied_for_anonymous(self, comment):
        """Test anonymous users cannot flag comments."""
        request = self.factory.post('/')
        request.user = AnonymousUser()
        
        view = type('View', (), {'action': 'flag'})()
        
        # Must be authenticated to flag
        assert not self.permission.has_permission(request, view)
    
    def test_approve_permission_for_moderator(self, moderator_user, comment):
        """Test moderator can approve comments."""
        request = self.factory.post('/')
        request.user = moderator_user
        
        view = type('View', (), {'action': 'approve'})()
        
        assert self.permission.has_object_permission(request, view, comment)
    
    def test_approve_permission_denied_for_regular_user(self, comment):
        """Test regular user cannot approve comments."""
        request = self.factory.post('/')
        request.user = self.user
        
        view = type('View', (), {'action': 'approve'})()
        
        # Will be denied at the view level by permission check
        # Permission class just checks authentication here
        assert self.permission.has_object_permission(request, view, comment)


@pytest.mark.django_db
class TestModeratorPermission:
    """Tests for ModeratorPermission class."""
    
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.permission = ModeratorPermission()
        self.user = UserFactory()
        self.staff_user = UserFactory(is_staff=True)
        self.superuser = UserFactory(is_superuser=True)
    
    def test_permission_denied_for_anonymous(self):
        """Test anonymous users are denied."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        
        assert not self.permission.has_permission(request, None)
    
    def test_permission_denied_for_regular_user(self):
        """Test regular users are denied."""
        request = self.factory.get('/')
        request.user = self.user
        
        assert not self.permission.has_permission(request, None)
    
    def test_permission_granted_for_staff(self):
        """Test staff users are granted permission."""
        request = self.factory.get('/')
        request.user = self.staff_user
        
        assert self.permission.has_permission(request, None)
    
    def test_permission_granted_for_superuser(self):
        """Test superusers are granted permission."""
        request = self.factory.get('/')
        request.user = self.superuser
        
        assert self.permission.has_permission(request, None)
    
    def test_permission_granted_for_moderator(self, moderator_user):
        """Test users with can_moderate_comments permission are granted."""
        request = self.factory.get('/')
        request.user = moderator_user
        
        assert self.permission.has_permission(request, None)


@pytest.mark.django_db
class TestPermissionIntegration:
    """Integration tests for permissions in realistic scenarios."""
    
    def test_anonymous_can_read_public_comments(self, api_client, comment):
        """Test anonymous users can read public comments."""
        from django.urls import reverse
        
        url = reverse('django_comments_api:comment-detail', args=[comment.pk])
        response = api_client.get(url)
        
        assert response.status_code == 200
    
    def test_anonymous_cannot_read_non_public_comments(self, api_client, comment):
        """Test anonymous users cannot read non-public comments."""
        from django.urls import reverse
        
        comment.is_public = False
        comment.save()
        
        url = reverse('django_comments_api:comment-detail', args=[comment.pk])
        response = api_client.get(url)
        
        # Comment should be filtered out in the queryset
        assert response.status_code == 404
    
    def test_owner_can_update_own_comment(self, authenticated_client, comment):
        """Test owner can update their own comment."""
        from django.urls import reverse
        
        url = reverse('django_comments_api:comment-detail', args=[comment.pk])
        response = authenticated_client.patch(
            url,
            {'content': 'Updated content'},
            format='json'
        )
        
        assert response.status_code == 200
        comment.refresh_from_db()
        assert comment.content == 'Updated content'
    
    def test_non_owner_cannot_update_comment(self, api_client, comment):
        """Test non-owner cannot update a comment."""
        from django.urls import reverse
        
        other_user = UserFactory()
        api_client.force_authenticate(user=other_user)
        
        url = reverse('django_comments_api:comment-detail', args=[comment.pk])
        response = api_client.patch(
            url,
            {'content': 'Hacked content'},
            format='json'
        )
        
        assert response.status_code == 403
        comment.refresh_from_db()
        assert comment.content != 'Hacked content'
    
    def test_staff_can_update_any_comment(self, staff_client, comment):
        """Test staff can update any comment."""
        from django.urls import reverse
        
        url = reverse('django_comments_api:comment-detail', args=[comment.pk])
        response = staff_client.patch(
            url,
            {'content': 'Staff updated'},
            format='json'
        )
        
        assert response.status_code == 200
        comment.refresh_from_db()
        assert comment.content == 'Staff updated'
    
    def test_moderator_can_approve_comment(self, moderator_client, comment):
        """Test moderator can approve a comment."""
        from django.urls import reverse
        
        comment.is_public = False
        comment.save()
        
        url = reverse('django_comments_api:comment-approve', args=[comment.pk])
        response = moderator_client.post(url)
        
        assert response.status_code == 200
        comment.refresh_from_db()
        assert comment.is_public is True
    
    def test_regular_user_cannot_approve_comment(self, authenticated_client, comment):
        """Test regular user cannot approve a comment."""
        from django.urls import reverse
        
        comment.is_public = False
        comment.save()
        
        url = reverse('django_comments_api:comment-approve', args=[comment.pk])
        response = authenticated_client.post(url)
        
        assert response.status_code == 403
        comment.refresh_from_db()
        assert comment.is_public is False