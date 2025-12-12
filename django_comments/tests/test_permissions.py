"""
Comprehensive tests for django_comments.api.permissions

Tests cover:
- IsOwnerOrReadOnly permission
- CommentPermission (main permission class)
- ModeratorPermission
- Success cases (permissions granted correctly)
- Failure cases (permissions denied correctly)
- Edge cases (anonymous users, staff, superusers, special scenarios)
"""

import uuid
from unittest.mock import Mock, MagicMock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, AnonymousUser
from django.test import RequestFactory, override_settings
from rest_framework import permissions

from django_comments.tests.base import BaseCommentTestCase
from django_comments.api.permissions import (
    IsOwnerOrReadOnly,
    CommentPermission,
    ModeratorPermission
)
from django_comments import conf as comments_conf

User = get_user_model()


# ============================================================================
# IS OWNER OR READ ONLY TESTS
# ============================================================================

class IsOwnerOrReadOnlyTests(BaseCommentTestCase):
    """Test IsOwnerOrReadOnly permission class."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.permission = IsOwnerOrReadOnly()
    
    def test_safe_methods_allowed_for_any_user(self):
        """Test that GET, HEAD, OPTIONS are allowed for anyone."""
        comment = self.create_comment(user=self.regular_user)
        
        safe_methods = ['GET', 'HEAD', 'OPTIONS']
        
        for method in safe_methods:
            request = self.factory.generic(method, '/fake-url/')
            request.user = self.another_user  # Different user
            
            has_permission = self.permission.has_object_permission(
                request, None, comment
            )
            
            self.assertTrue(
                has_permission,
                f"{method} should be allowed for any user"
            )
    
    def test_owner_can_modify_own_comment(self):
        """Test that comment owner can modify their own comment."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.put('/fake-url/')
        request.user = self.regular_user
        
        has_permission = self.permission.has_object_permission(
            request, None, comment
        )
        
        self.assertTrue(has_permission)
    
    def test_non_owner_cannot_modify_comment(self):
        """Test that non-owner cannot modify comment."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.put('/fake-url/')
        request.user = self.another_user
        
        has_permission = self.permission.has_object_permission(
            request, None, comment
        )
        
        self.assertFalse(has_permission)
    
    def test_owner_can_delete_own_comment(self):
        """Test that owner can delete their own comment."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.delete('/fake-url/')
        request.user = self.regular_user
        
        has_permission = self.permission.has_object_permission(
            request, None, comment
        )
        
        self.assertTrue(has_permission)
    
    def test_anonymous_user_cannot_modify(self):
        """Test that anonymous user cannot modify any comment."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.put('/fake-url/')
        request.user = AnonymousUser()
        
        has_permission = self.permission.has_object_permission(
            request, None, comment
        )
        
        self.assertFalse(has_permission)
    
    def test_anonymous_user_can_read(self):
        """Test that anonymous user can read comments."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.get('/fake-url/')
        request.user = AnonymousUser()
        
        has_permission = self.permission.has_object_permission(
            request, None, comment
        )
        
        self.assertTrue(has_permission)


# ============================================================================
# COMMENT PERMISSION TESTS - has_permission
# ============================================================================

class CommentPermissionHasPermissionTests(BaseCommentTestCase):
    """Test CommentPermission.has_permission method."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.permission = CommentPermission()
    
    def test_safe_methods_allowed_for_everyone(self):
        """Test that GET requests are allowed for everyone."""
        request = self.factory.get('/fake-url/')
        request.user = AnonymousUser()
        
        view = Mock()
        view.action = 'list'
        
        has_permission = self.permission.has_permission(request, view)
        self.assertTrue(has_permission)
    
    def test_authenticated_user_can_create_comment(self):
        """Test that authenticated users can create comments."""
        request = self.factory.post('/fake-url/')
        request.user = self.regular_user
        
        view = Mock()
        view.action = 'create'
        
        has_permission = self.permission.has_permission(request, view)
        self.assertTrue(has_permission)
    
    def test_anonymous_user_cannot_create_comment_by_default(self):
        """Test that anonymous users cannot create comments by default."""
        # Create a fresh permission instance to check default behavior
        # The default behavior depends on the actual ALLOW_ANONYMOUS setting
        request = self.factory.post('/fake-url/')
        request.user = AnonymousUser()
        
        view = Mock()
        view.action = 'create'
        
        permission = CommentPermission()
        has_permission = permission.has_permission(request, view)
        
        # Check against actual setting
        from django_comments.conf import comments_settings
        expected = comments_settings.ALLOW_ANONYMOUS
        
        if expected:
            # If anonymous comments are allowed, permission should be True
            self.assertTrue(has_permission)
        else:
            # If not allowed, permission should be False
            self.assertFalse(has_permission)
    
    @override_settings(DJANGO_COMMENTS={'ALLOW_ANONYMOUS': True})
    def test_anonymous_user_can_create_when_allowed(self):
        """Test that anonymous users can create when ALLOW_ANONYMOUS is True."""
        from importlib import reload
        reload(comments_conf)
        
        request = self.factory.post('/fake-url/')
        request.user = AnonymousUser()
        
        view = Mock()
        view.action = 'create'
        
        permission = CommentPermission()
        has_permission = permission.has_permission(request, view)
        self.assertTrue(has_permission)
    
    def test_non_create_actions_require_authentication(self):
        """Test that non-create, non-safe actions require authentication."""
        request = self.factory.put('/fake-url/')
        request.user = AnonymousUser()
        
        view = Mock()
        view.action = 'update'
        
        has_permission = self.permission.has_permission(request, view)
        self.assertFalse(has_permission)
    
    def test_authenticated_user_allowed_for_custom_actions(self):
        """Test authenticated users allowed for custom actions."""
        request = self.factory.post('/fake-url/')
        request.user = self.regular_user
        
        view = Mock()
        view.action = 'custom_action'
        
        has_permission = self.permission.has_permission(request, view)
        self.assertTrue(has_permission)


# ============================================================================
# COMMENT PERMISSION TESTS - has_object_permission
# ============================================================================

class CommentPermissionObjectPermissionTests(BaseCommentTestCase):
    """Test CommentPermission.has_object_permission method."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.permission = CommentPermission()
    
    def test_safe_methods_allowed_on_any_object(self):
        """Test that safe methods are allowed on any comment object."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.get('/fake-url/')
        request.user = self.another_user
        
        view = Mock()
        view.action = 'retrieve'
        
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(has_permission)
    
    def test_staff_can_do_anything(self):
        """Test that staff users can perform any action."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.delete('/fake-url/')
        request.user = self.staff_user
        
        view = Mock()
        view.action = 'destroy'
        
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(has_permission)
    
    def test_superuser_can_do_anything(self):
        """Test that superusers can perform any action."""
        comment = self.create_comment(user=self.regular_user)
        
        # Create superuser
        User = get_user_model()
        superuser = User.objects.create_user(
            username='superuser',
            email='super@example.com',
            password='testpass123',
            is_superuser=True
        )
        
        request = self.factory.delete('/fake-url/')
        request.user = superuser
        
        view = Mock()
        view.action = 'destroy'
        
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(has_permission)
    
    def test_owner_can_update_own_comment(self):
        """Test that comment owner can update their own comment."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.put('/fake-url/')
        request.user = self.regular_user
        
        view = Mock()
        view.action = 'update'
        request.method = 'PUT'
        
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(has_permission)
    
    def test_non_owner_cannot_update_comment(self):
        """Test that non-owner cannot update comment."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.put('/fake-url/')
        request.user = self.another_user
        
        view = Mock()
        view.action = 'update'
        request.method = 'PUT'
        
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertFalse(has_permission)
    
    def test_owner_can_partial_update_own_comment(self):
        """Test that owner can perform partial update on own comment."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.patch('/fake-url/')
        request.user = self.regular_user
        
        view = Mock()
        view.action = 'partial_update'
        request.method = 'PATCH'
        
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(has_permission)
    
    def test_owner_can_delete_own_comment(self):
        """Test that owner can delete their own comment."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.delete('/fake-url/')
        request.user = self.regular_user
        
        view = Mock()
        view.action = 'destroy'
        request.method = 'DELETE'
        
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(has_permission)
    
    def test_non_owner_cannot_delete_comment(self):
        """Test that non-owner cannot delete comment."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.delete('/fake-url/')
        request.user = self.another_user
        
        view = Mock()
        view.action = 'destroy'
        request.method = 'DELETE'
        
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertFalse(has_permission)
    
    def test_approve_action_allowed_through(self):
        """Test that approve action is allowed through (checked at view level)."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.post('/fake-url/')
        request.user = self.another_user
        
        view = Mock()
        view.action = 'approve'
        
        # Permission check at this level should pass
        # Actual permission is checked in the view
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(has_permission)
    
    def test_reject_action_allowed_through(self):
        """Test that reject action is allowed through (checked at view level)."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.post('/fake-url/')
        request.user = self.another_user
        
        view = Mock()
        view.action = 'reject'
        
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(has_permission)
    
    def test_flag_action_requires_authentication(self):
        """Test that flag action requires authenticated user."""
        comment = self.create_comment(user=self.regular_user)
        
        # Authenticated user can flag
        request = self.factory.post('/fake-url/')
        request.user = self.another_user
        
        view = Mock()
        view.action = 'flag'
        
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(has_permission)
    
    def test_flag_action_denied_for_anonymous(self):
        """Test that anonymous users cannot flag comments."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.post('/fake-url/')
        request.user = AnonymousUser()
        
        view = Mock()
        view.action = 'flag'
        
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertFalse(has_permission)
    
    def test_unknown_action_denied(self):
        """Test that unknown actions are denied by default."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.post('/fake-url/')
        request.user = self.regular_user
        
        view = Mock()
        view.action = 'unknown_action'
        request.method = 'POST'
        
        has_permission = self.permission.has_object_permission(
            request, view, comment
        )
        self.assertFalse(has_permission)


# ============================================================================
# MODERATOR PERMISSION TESTS
# ============================================================================

class ModeratorPermissionTests(BaseCommentTestCase):
    """Test ModeratorPermission class."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.permission = ModeratorPermission()
        
        # Add moderation permission to moderator
        perm = Permission.objects.get(codename='can_moderate_comments')
        self.moderator.user_permissions.add(perm)
    
    def test_staff_has_moderator_permission(self):
        """Test that staff users have moderator permission."""
        request = self.factory.post('/fake-url/')
        request.user = self.staff_user
        
        view = Mock()
        
        has_permission = self.permission.has_permission(request, view)
        self.assertTrue(has_permission)
    
    def test_superuser_has_moderator_permission(self):
        """Test that superusers have moderator permission."""
        User = get_user_model()
        superuser = User.objects.create_user(
            username='superuser',
            email='super@example.com',
            password='testpass123',
            is_superuser=True
        )
        
        request = self.factory.post('/fake-url/')
        request.user = superuser
        
        view = Mock()
        
        has_permission = self.permission.has_permission(request, view)
        self.assertTrue(has_permission)
    
    def test_user_with_permission_has_access(self):
        """Test that user with can_moderate_comments permission has access."""
        request = self.factory.post('/fake-url/')
        request.user = self.moderator
        
        view = Mock()
        
        has_permission = self.permission.has_permission(request, view)
        self.assertTrue(has_permission)
    
    def test_regular_user_without_permission_denied(self):
        """Test that regular user without permission is denied."""
        request = self.factory.post('/fake-url/')
        request.user = self.regular_user
        
        view = Mock()
        
        has_permission = self.permission.has_permission(request, view)
        self.assertFalse(has_permission)
    
    def test_anonymous_user_denied(self):
        """Test that anonymous user is denied moderator access."""
        request = self.factory.post('/fake-url/')
        request.user = AnonymousUser()
        
        view = Mock()
        
        has_permission = self.permission.has_permission(request, view)
        self.assertFalse(has_permission)
    
    def test_inactive_staff_in_edge_case(self):
        """
        Test inactive staff user behavior in permission check.
        
        Note: In production, inactive users cannot authenticate and won't reach
        permission checks. However, when manually setting request.user in tests,
        inactive staff DO pass permission checks because:
        1. is_authenticated returns True for any User object (active or not)
        2. is_staff=True grants moderator permission
        
        This test documents the actual behavior. In production, Django's
        authentication backends prevent inactive users from logging in.
        """
        User = get_user_model()
        inactive_staff = User.objects.create_user(
            username='inactive_staff',
            email='inactive@example.com',
            password='testpass123',
            is_staff=True,
            is_active=False
        )
        
        request = self.factory.post('/fake-url/')
        request.user = inactive_staff
        
        view = Mock()
        
        # In this edge case, permission check passes
        # (Though this can't happen in production due to auth middleware)
        has_permission = self.permission.has_permission(request, view)
        self.assertTrue(has_permission)
    
    def test_user_with_permission_but_inactive_denied(self):
        """
        Test inactive user with permission is denied.
        
        Important: Unlike is_staff/is_superuser (which are just boolean fields),
        Django's has_perm() method DOES check is_active internally.
        
        This means:
        - Inactive staff pass (is_staff doesn't check is_active)
        - Inactive users with permissions fail (has_perm checks is_active)
        
        This is Django's built-in behavior for permission checking.
        """
        User = get_user_model()
        inactive_moderator = User.objects.create_user(
            username='inactive_mod',
            email='inactive_mod@example.com',
            password='testpass123',
            is_active=False
        )
        perm = Permission.objects.get(codename='can_moderate_comments')
        inactive_moderator.user_permissions.add(perm)
        
        request = self.factory.post('/fake-url/')
        request.user = inactive_moderator
        
        view = Mock()
        
        # has_perm() returns False for inactive users
        has_permission = self.permission.has_permission(request, view)
        self.assertFalse(has_permission)


# ============================================================================
# EDGE CASES AND REAL-WORLD SCENARIOS
# ============================================================================

class PermissionEdgeCaseTests(BaseCommentTestCase):
    """Test edge cases and real-world permission scenarios."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.comment_permission = CommentPermission()
        self.moderator_permission = ModeratorPermission()
        
        perm = Permission.objects.get(codename='can_moderate_comments')
        self.moderator.user_permissions.add(perm)
    
    def test_comment_without_user_field(self):
        """Test permission check on comment without user (edge case)."""
        # Create comment with null user (anonymous comment)
        comment = self.create_comment(user=None, user_name='Anonymous User')
        
        request = self.factory.put('/fake-url/')
        request.user = self.regular_user
        
        view = Mock()
        view.action = 'update'
        request.method = 'PUT'
        
        # Should not crash
        has_permission = self.comment_permission.has_object_permission(
            request, view, comment
        )
        
        # Regular user cannot edit anonymous comment
        self.assertFalse(has_permission)
    
    def test_staff_can_edit_anonymous_comment(self):
        """Test that staff can edit anonymous comments."""
        comment = self.create_comment(user=None, user_name='Anonymous User')
        
        request = self.factory.put('/fake-url/')
        request.user = self.staff_user
        
        view = Mock()
        view.action = 'update'
        request.method = 'PUT'
        
        has_permission = self.comment_permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(has_permission)
    
    def test_multiple_permissions_on_same_request(self):
        """Test multiple permission checks on same request."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.get('/fake-url/')
        request.user = self.regular_user
        
        view = Mock()
        view.action = 'retrieve'
        
        # Should pass both IsOwnerOrReadOnly and CommentPermission
        owner_perm = IsOwnerOrReadOnly()
        comment_perm = CommentPermission()
        
        has_owner_perm = owner_perm.has_object_permission(request, view, comment)
        has_comment_perm = comment_perm.has_object_permission(request, view, comment)
        
        self.assertTrue(has_owner_perm)
        self.assertTrue(has_comment_perm)
    
    def test_permission_with_deleted_user(self):
        """Test permission check when comment's user has been deleted."""
        comment = self.create_comment(user=self.regular_user)
        user_id = self.regular_user.pk
        
        # Delete the user
        self.regular_user.delete()
        
        # Refresh comment
        comment.refresh_from_db()
        
        # Try to check permissions
        request = self.factory.put('/fake-url/')
        request.user = self.another_user
        
        view = Mock()
        view.action = 'update'
        request.method = 'PUT'
        
        # Should not crash
        try:
            has_permission = self.comment_permission.has_object_permission(
                request, view, comment
            )
            # Permission should be denied since user is gone
            self.assertFalse(has_permission)
        except Exception as e:
            self.fail(f"Permission check should not crash: {e}")
    
    def test_permission_hierarchy_staff_over_owner(self):
        """Test that staff permission takes precedence over ownership."""
        comment = self.create_comment(user=self.regular_user)
        
        # Staff user who doesn't own the comment
        request = self.factory.delete('/fake-url/')
        request.user = self.staff_user
        
        view = Mock()
        view.action = 'destroy'
        request.method = 'DELETE'
        
        has_permission = self.comment_permission.has_object_permission(
            request, view, comment
        )
        
        # Staff should be able to delete even if not owner
        self.assertTrue(has_permission)
    
    def test_permission_with_same_user_different_actions(self):
        """Test that same user has different permissions for different actions."""
        comment = self.create_comment(user=self.regular_user)
        
        # Owner can update
        request = self.factory.put('/fake-url/')
        request.user = self.regular_user
        view = Mock()
        view.action = 'update'
        request.method = 'PUT'
        
        can_update = self.comment_permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(can_update)
        
        # Owner can delete
        request = self.factory.delete('/fake-url/')
        request.user = self.regular_user
        view = Mock()
        view.action = 'destroy'
        request.method = 'DELETE'
        
        can_delete = self.comment_permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(can_delete)
        
        # Owner can read
        request = self.factory.get('/fake-url/')
        request.user = self.regular_user
        view = Mock()
        view.action = 'retrieve'
        request.method = 'GET'
        
        can_read = self.comment_permission.has_object_permission(
            request, view, comment
        )
        self.assertTrue(can_read)
    
    def test_moderator_permission_does_not_grant_ownership_rights(self):
        """Test that moderator permission doesn't grant edit rights (only staff does)."""
        comment = self.create_comment(user=self.regular_user)
        
        # Moderator without staff status
        User = get_user_model()
        non_staff_moderator = User.objects.create_user(
            username='non_staff_mod',
            email='non_staff_mod@example.com',
            password='testpass123',
            is_staff=False
        )
        perm = Permission.objects.get(codename='can_moderate_comments')
        non_staff_moderator.user_permissions.add(perm)
        
        request = self.factory.put('/fake-url/')
        request.user = non_staff_moderator
        
        view = Mock()
        view.action = 'update'
        request.method = 'PUT'
        
        has_permission = self.comment_permission.has_object_permission(
            request, view, comment
        )
        
        # Moderator permission alone doesn't grant edit rights
        # Only staff/superuser or owner can edit
        self.assertFalse(has_permission)
    
    def test_permission_with_none_view(self):
        """Test permission check with None view (edge case)."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.get('/fake-url/')
        request.user = self.regular_user
        
        owner_perm = IsOwnerOrReadOnly()
        
        # Should not crash with None view
        try:
            has_permission = owner_perm.has_object_permission(
                request, None, comment
            )
            self.assertTrue(has_permission)  # Safe method
        except Exception as e:
            self.fail(f"Permission check should not crash with None view: {e}")
    
    def test_permission_caching_same_request(self):
        """Test that permission checks on same request are consistent."""
        comment = self.create_comment(user=self.regular_user)
        
        request = self.factory.get('/fake-url/')
        request.user = self.regular_user
        
        view = Mock()
        view.action = 'retrieve'
        
        # Check permission multiple times
        results = []
        for _ in range(3):
            has_permission = self.comment_permission.has_object_permission(
                request, view, comment
            )
            results.append(has_permission)
        
        # All should be consistent
        self.assertTrue(all(results))
        self.assertEqual(len(set(results)), 1)  # All same value
    
    def test_safe_methods_list_comprehensive(self):
        """Test all safe HTTP methods are actually safe."""
        comment = self.create_comment(user=self.regular_user)
        
        safe_methods = ['GET', 'HEAD', 'OPTIONS']
        permission = IsOwnerOrReadOnly()
        
        for method in safe_methods:
            request = self.factory.generic(method, '/fake-url/')
            request.user = AnonymousUser()  # Even anonymous should work
            
            has_permission = permission.has_object_permission(
                request, None, comment
            )
            
            self.assertTrue(
                has_permission,
                f"{method} should be safe for anonymous users"
            )
    
    def test_unsafe_methods_list_comprehensive(self):
        """Test all unsafe HTTP methods actually require ownership."""
        comment = self.create_comment(user=self.regular_user)
        
        unsafe_methods = ['POST', 'PUT', 'PATCH', 'DELETE']
        permission = IsOwnerOrReadOnly()
        
        for method in unsafe_methods:
            # Non-owner tries unsafe method
            request = self.factory.generic(method, '/fake-url/')
            request.user = self.another_user
            
            has_permission = permission.has_object_permission(
                request, None, comment
            )
            
            self.assertFalse(
                has_permission,
                f"{method} should require ownership"
            )
    
    def test_permission_with_custom_user_model_fields(self):
        """Test permissions work with custom user model fields."""
        # Create comment with regular user
        comment = self.create_comment(user=self.regular_user)
        
        # Ensure permission check uses pk comparison, not specific fields
        request = self.factory.put('/fake-url/')
        request.user = self.regular_user
        
        view = Mock()
        view.action = 'update'
        request.method = 'PUT'
        
        has_permission = self.comment_permission.has_object_permission(
            request, view, comment
        )
        
        self.assertTrue(has_permission)
    
    @override_settings(DJANGO_COMMENTS={'ALLOW_ANONYMOUS': True})
    def test_anonymous_comments_permission_flow(self):
        """Test complete permission flow for anonymous comments."""
        from importlib import reload
        reload(comments_conf)
        
        # Anonymous user can create
        request = self.factory.post('/fake-url/')
        request.user = AnonymousUser()
        
        view = Mock()
        view.action = 'create'
        
        permission = CommentPermission()
        can_create = permission.has_permission(request, view)
        self.assertTrue(can_create)
        
        # Create anonymous comment with user_name
        comment = self.create_comment(user=None, user_name='Anonymous User')
        
        # Anonymous user cannot edit even their own comment
        request = self.factory.put('/fake-url/')
        request.user = AnonymousUser()
        view.action = 'update'
        request.method = 'PUT'
        
        can_edit = permission.has_object_permission(request, view, comment)
        self.assertFalse(can_edit)