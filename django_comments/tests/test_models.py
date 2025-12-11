"""
Comprehensive Test Suite for Comment Model

Tests cover:
- Comment creation (authenticated and anonymous)
- UUID primary key functionality
- Generic foreign key with different PK types (int, UUID, custom)
- Comment threading and nesting
- Path and thread_id management
- Moderation states (is_public, is_removed)
- Validation rules
- Model methods (get_children, get_ancestors, depth, etc.)
- Manager and queryset methods
- Edge cases (max depth, max length, special characters, etc.)
- Performance optimizations
"""
import uuid
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta

from .base import BaseCommentTestCase


class CommentModelCreationTests(BaseCommentTestCase):
    """
    Test Comment model creation with various scenarios.
    """
    
    def test_create_basic_comment_success(self):
        """Test creating a basic comment with required fields."""
        comment = self.create_comment(
            content='This is a test comment about Django development.'
        )
        
        self.assertCommentValid(comment)
        self.assertCommentPublic(comment)
        self.assertEqual(comment.user, self.regular_user)
        self.assertEqual(comment.content_type, self.content_type)
        self.assertEqual(comment.object_id, self.test_obj_id)
    
    def test_comment_has_uuid_primary_key(self):
        """Test that Comment uses UUID as primary key."""
        comment = self.create_comment()
        
        self.assertIsInstance(comment.pk, uuid.UUID)
        self.assertIsInstance(comment.id, uuid.UUID)
        self.assertEqual(comment.pk, comment.id)
    
    def test_comment_uuid_is_unique(self):
        """Test that each comment gets a unique UUID."""
        comment1 = self.create_comment(content='First comment')
        comment2 = self.create_comment(content='Second comment')
        
        self.assertNotEqual(comment1.pk, comment2.pk)
    
    def test_create_anonymous_comment_success(self):
        """Test creating comment without authenticated user."""
        comment = self.create_anonymous_comment(
            user_name='Guest User',
            user_email='guest@example.com',
            content='Anonymous comment content'
        )
        
        self.assertCommentValid(comment)
        self.assertIsNone(comment.user)
        self.assertEqual(comment.user_name, 'Guest User')
        self.assertEqual(comment.user_email, 'guest@example.com')
    
    def test_create_comment_with_ip_address(self):
        """Test storing IP address with comment."""
        comment = self.create_comment(
            ip_address='192.168.1.100',
            content='Comment from specific IP'
        )
        
        self.assertEqual(comment.ip_address, '192.168.1.100')
    
    def test_create_comment_with_ipv6_address(self):
        """Test storing IPv6 address with comment."""
        comment = self.create_comment(
            ip_address='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
            content='Comment from IPv6'
        )
        
        self.assertEqual(
            comment.ip_address,
            '2001:0db8:85a3:0000:0000:8a2e:0370:7334'
        )
    
    def test_create_comment_with_user_agent(self):
        """Test storing user agent string with comment."""
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        comment = self.create_comment(
            user_agent=user_agent,
            content='Comment with user agent'
        )
        
        self.assertEqual(comment.user_agent, user_agent)
    
    def test_create_comment_not_public(self):
        """Test creating comment that requires moderation."""
        comment = self.create_comment(
            is_public=False,
            content='This comment requires moderation'
        )
        
        self.assertFalse(comment.is_public)
        self.assertCommentValid(comment)
    
    def test_create_removed_comment(self):
        """Test creating comment marked as removed."""
        comment = self.create_comment(
            is_removed=True,
            content='This comment was removed'
        )
        
        self.assertTrue(comment.is_removed)
        self.assertCommentValid(comment)


class CommentGenericForeignKeyTests(BaseCommentTestCase):
    """
    Test Comment's generic foreign key functionality with different PK types.
    """
    
    def test_comment_on_object_with_integer_pk(self):
        """Test commenting on object with integer primary key."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # User model has integer PK
        user = self.regular_user
        content_type = ContentType.objects.get_for_model(User)
        
        comment = self.Comment.objects.create(
            content_type=content_type,
            object_id=str(user.pk),  # Convert int to string
            user=self.moderator,
            content='Comment on user with integer PK'
        )
        
        self.assertEqual(comment.content_object, user)
        self.assertEqual(comment.object_id, str(user.pk))
    
    def test_comment_on_object_with_uuid_pk(self):
        """Test commenting on object with UUID primary key."""
        # Comment itself has UUID PK
        first_comment = self.create_comment(content='First comment')
        
        # Create reply (comment on a comment)
        reply = self.Comment.objects.create(
            content_type=ContentType.objects.get_for_model(self.Comment),
            object_id=str(first_comment.pk),
            user=self.another_user,
            content='Reply to UUID-based object'
        )
        
        self.assertEqual(reply.content_object, first_comment)
        self.assertEqual(reply.object_id, str(first_comment.pk))
    
    def test_comment_object_id_stored_as_string(self):
        """Test that object_id is always stored as string."""
        comment = self.create_comment()
        
        self.assertIsInstance(comment.object_id, str)
        self.assertEqual(comment.object_id, str(self.test_obj.pk))
    
    def test_comment_content_object_retrieval(self):
        """Test that content_object properly retrieves the related object."""
        comment = self.create_comment()
        
        retrieved_obj = comment.content_object
        self.assertEqual(retrieved_obj, self.test_obj)
        self.assertEqual(retrieved_obj.pk, self.test_obj.pk)


class CommentThreadingTests(BaseCommentTestCase):
    """
    Test Comment threading and hierarchical structure.
    """
    
    def test_create_root_comment(self):
        """Test creating a root-level comment (no parent)."""
        comment = self.create_comment(content='Root comment')
        
        self.assertIsNone(comment.parent)
        self.assertEqual(comment.depth, 0)
        self.assertIsNotNone(comment.path)
    
    def test_create_reply_to_comment(self):
        """Test creating a reply to existing comment."""
        parent = self.create_comment(content='Parent comment')
        reply = self.create_comment(
            parent=parent,
            content='Reply to parent'
        )
        
        self.assertEqual(reply.parent, parent)
        self.assertGreater(reply.depth, parent.depth)
        self.assertTrue(reply.path.startswith(parent.path))
    
    def test_nested_replies_maintain_hierarchy(self):
        """Test deeply nested replies maintain correct hierarchy."""
        root = self.create_comment(content='Root')
        level1 = self.create_comment(parent=root, content='Level 1')
        level2 = self.create_comment(parent=level1, content='Level 2')
        level3 = self.create_comment(parent=level2, content='Level 3')
        
        self.assertEqual(root.depth, 0)
        self.assertEqual(level1.depth, 1)
        self.assertEqual(level2.depth, 2)
        self.assertEqual(level3.depth, 3)
        
        self.assertIn(root.path, level1.path)
        self.assertIn(level1.path, level2.path)
        self.assertIn(level2.path, level3.path)
    
    def test_get_children_returns_direct_replies(self):
        """Test get_children returns only direct replies."""
        parent = self.create_comment(content='Parent')
        child1 = self.create_comment(parent=parent, content='Child 1')
        child2 = self.create_comment(parent=parent, content='Child 2')
        grandchild = self.create_comment(parent=child1, content='Grandchild')
        
        children = list(parent.children.all())
        
        self.assertEqual(len(children), 2)
        self.assertIn(child1, children)
        self.assertIn(child2, children)
        self.assertNotIn(grandchild, children)
    
    def test_get_descendants_returns_all_nested_replies(self):
        """Test get_descendants returns all nested replies."""
        parent = self.create_comment(content='Parent')
        child1 = self.create_comment(parent=parent, content='Child 1')
        child2 = self.create_comment(parent=parent, content='Child 2')
        grandchild1 = self.create_comment(parent=child1, content='Grandchild 1')
        grandchild2 = self.create_comment(parent=child2, content='Grandchild 2')
        
        descendants = list(parent.get_descendants())
        
        self.assertEqual(len(descendants), 4)
        self.assertIn(child1, descendants)
        self.assertIn(child2, descendants)
        self.assertIn(grandchild1, descendants)
        self.assertIn(grandchild2, descendants)
    
    def test_get_ancestors_returns_parent_chain(self):
        """Test get_ancestors returns all parents up to root."""
        root = self.create_comment(content='Root')
        level1 = self.create_comment(parent=root, content='Level 1')
        level2 = self.create_comment(parent=level1, content='Level 2')
        level3 = self.create_comment(parent=level2, content='Level 3')
        
        ancestors = list(level3.get_ancestors())
        
        self.assertEqual(len(ancestors), 3)
        self.assertIn(root, ancestors)
        self.assertIn(level1, ancestors)
        self.assertIn(level2, ancestors)
    
    def test_path_calculation_is_correct(self):
        """Test that materialized path is calculated correctly."""
        parent = self.create_comment(content='Parent')
        child = self.create_comment(parent=parent, content='Child')
        
        # Path should contain parent's ID and be hierarchical
        self.assertIsNotNone(parent.path)
        self.assertIsNotNone(child.path)
        self.assertIn(str(parent.pk), child.path)
        self.assertTrue(child.path.startswith(parent.path + '/'))
    
    def test_thread_id_same_for_thread_members(self):
        """Test that all comments in same thread share thread_id."""
        root = self.create_comment(content='Root')
        child1 = self.create_comment(parent=root, content='Child 1')
        grandchild = self.create_comment(parent=child1, content='Grandchild')
        
        # All should have same thread_id (root's PK)
        self.assertEqual(root.thread_id, str(root.pk))
        self.assertEqual(child1.thread_id, str(root.pk))
        self.assertEqual(grandchild.thread_id, str(root.pk))


class CommentValidationTests(BaseCommentTestCase):
    """
    Test Comment model validation rules.
    """
    
    def test_create_comment_without_content_fails(self):
        """Test that comment without content fails validation."""
        with self.assertRaises(ValidationError):
            comment = self.Comment(
                content_type=self.content_type,
                object_id=self.test_obj_id,
                user=self.regular_user,
                content=''  # Empty content
            )
            comment.full_clean()
    
    def test_create_comment_with_only_whitespace_fails(self):
        """Test that comment with only whitespace fails validation."""
        with self.assertRaises(ValidationError):
            comment = self.Comment(
                content_type=self.content_type,
                object_id=self.test_obj_id,
                user=self.regular_user,
                content='   \n\t   '  # Only whitespace
            )
            comment.full_clean()
    
    @override_settings(DJANGO_COMMENTS={'MAX_COMMENT_LENGTH': 100})
    def test_create_comment_exceeding_max_length_fails(self):
        """Test that comment exceeding max length fails validation."""
        long_content = 'x' * 200
        
        with self.assertRaises(ValidationError):
            comment = self.Comment(
                content_type=self.content_type,
                object_id=self.test_obj_id,
                user=self.regular_user,
                content=long_content
            )
            comment.full_clean()  # ✅ Explicitly call validation
    
    def test_anonymous_comment_requires_name_or_email(self):
        """Test that anonymous comment needs user_name or user_email."""
        comment = self.Comment(
            content_type=self.content_type,
            object_id=self.test_obj_id,
            user=None,  # Anonymous
            user_name='',
            user_email='',
            content='Anonymous comment'
        )
        
        with self.assertRaises(ValidationError) as cm:
            comment.full_clean()
        
        self.assertIn('user', str(cm.exception).lower())
    
    def test_anonymous_comment_with_name_succeeds(self):
        """Test that anonymous comment with user_name is valid."""
        comment = self.Comment(
            content_type=self.content_type,
            object_id=self.test_obj_id,
            user=None,
            user_name='Anonymous Commenter',
            user_email='',
            content='Valid anonymous comment'
        )
        
        comment.full_clean()  # Should not raise
        comment.save()
        self.assertCommentValid(comment)
    
    def test_authenticated_comment_ignores_user_name(self):
        """Test that authenticated comment doesn't require user_name."""
        comment = self.Comment(
            content_type=self.content_type,
            object_id=self.test_obj_id,
            user=self.regular_user,
            user_name='',  # Empty is OK for authenticated
            content='Authenticated comment'
        )
        
        comment.full_clean()  # Should not raise
        comment.save()
        self.assertCommentValid(comment)


class CommentMaxDepthTests(BaseCommentTestCase):
    """
    Test maximum comment depth enforcement.
    """
    
    @override_settings(DJANGO_COMMENTS={'MAX_COMMENT_DEPTH': 3})
    def test_enforce_max_depth_prevents_deep_nesting(self):
        """Test that MAX_COMMENT_DEPTH setting prevents too deep nesting."""
        root = self.create_comment(content='Root')
        level1 = self.create_comment(parent=root, content='Level 1')
        level2 = self.create_comment(parent=level1, content='Level 2')
        level3 = self.create_comment(parent=level2, content='Level 3')
        
        # Trying to create level 4 should fail
        with self.assertRaises(ValidationError) as cm:
            level4 = self.Comment(
                content_type=self.content_type,
                object_id=self.test_obj_id,
                user=self.regular_user,
                parent=level3,
                content='Level 4 - should fail'
            )
            level4.full_clean()
        
        self.assertIn('depth', str(cm.exception).lower())
    
    @override_settings(DJANGO_COMMENTS={'MAX_COMMENT_DEPTH': None})
    def test_unlimited_depth_when_max_depth_none(self):
        """Test that None allows unlimited depth."""
        parent = self.create_comment(content='Root')
        
        # Create 10 levels deep
        for i in range(10):
            parent = self.create_comment(
                parent=parent,
                content=f'Level {i + 1}'
            )
        
        self.assertEqual(parent.depth, 10)
    
    @override_settings(DJANGO_COMMENTS={'MAX_COMMENT_DEPTH': 1})
    def test_max_depth_one_allows_only_root_and_replies(self):
        """Test MAX_COMMENT_DEPTH=1 allows root + 1 level of replies."""
        root = self.create_comment(content='Root')
        reply = self.create_comment(parent=root, content='Reply')
        
        # Second level reply should fail
        with self.assertRaises(ValidationError):
            nested_reply = self.Comment(
                content_type=self.content_type,
                object_id=self.test_obj_id,
                user=self.regular_user,
                parent=reply,
                content='Nested reply - should fail'
            )
            nested_reply.full_clean()


class CommentModelMethodTests(BaseCommentTestCase):
    """
    Test Comment model methods.
    """
    
    def test_str_representation_with_user(self):
        """Test string representation of comment with authenticated user."""
        comment = self.create_comment(
            content='Test comment for string representation'
        )
        
        str_repr = str(comment)
        self.assertIn(self.regular_user.username, str_repr)
        self.assertIn('Comment', str_repr)
    
    def test_str_representation_anonymous(self):
        """Test string representation of anonymous comment."""
        comment = self.create_anonymous_comment(
            user_name='Guest',
            content='Anonymous comment'
        )
        
        str_repr = str(comment)
        # Should show user_name or indicate anonymous
        self.assertTrue('Guest' in str_repr or 'Anonymous' in str_repr)
    
    def test_get_user_name_authenticated(self):
        """Test get_user_name returns username for authenticated user."""
        comment = self.create_comment()
        
        user_name = comment.get_user_name()
        self.assertIn(self.regular_user.get_full_name() or self.regular_user.username, user_name)
    
    def test_get_user_name_anonymous_with_name(self):
        """Test get_user_name returns user_name for anonymous."""
        comment = self.create_anonymous_comment(
            user_name='Guest Commenter'
        )
        
        user_name = comment.get_user_name()
        self.assertEqual(user_name, 'Guest Commenter')
    
    def test_depth_property_root_comment(self):
        """Test depth property returns 0 for root comment."""
        comment = self.create_comment()
        self.assertEqual(comment.depth, 0)
    
    def test_depth_property_nested_comment(self):
        """Test depth property returns correct depth for nested comment."""
        root = self.create_comment(content='Root')
        level1 = self.create_comment(parent=root, content='Level 1')
        level2 = self.create_comment(parent=level1, content='Level 2')
        
        self.assertEqual(level2.depth, 2)
    
    def test_is_edited_property_grace_period(self):
        """Test is_edited respects 30-second grace period."""
        comment = self.create_comment()
        
        # Immediately after creation
        self.assertFalse(comment.is_edited)
        
        # Simulate edit within grace period
        comment.content = 'Updated content'
        comment.save()
        fresh_comment = self.get_fresh_comment(comment)
        
        # If updated within 30 seconds, still not "edited"
        time_diff = fresh_comment.updated_at - fresh_comment.created_at
        if time_diff.total_seconds() <= 30:
            self.assertFalse(fresh_comment.is_edited)
    
    def test_is_edited_property_after_grace_period(self):
        """Test is_edited returns True after grace period."""
        comment = self.create_comment()
        
        # Simulate edit after grace period
        comment.created_at = timezone.now() - timedelta(minutes=5)
        comment.updated_at = timezone.now()
        comment.save(update_fields=['created_at', 'updated_at'])
        
        fresh_comment = self.get_fresh_comment(comment)
        self.assertTrue(fresh_comment.is_edited)


class CommentTimestampTests(BaseCommentTestCase):
    """
    Test Comment timestamp fields (created_at, updated_at).
    """
    
    def test_created_at_set_on_creation(self):
        """Test created_at is automatically set when comment is created."""
        before = timezone.now()
        comment = self.create_comment()
        after = timezone.now()
        
        self.assertIsNotNone(comment.created_at)
        self.assertGreaterEqual(comment.created_at, before)
        self.assertLessEqual(comment.created_at, after)
    
    def test_updated_at_set_on_creation(self):
        """Test updated_at is set when comment is created."""
        comment = self.create_comment()
        
        self.assertIsNotNone(comment.updated_at)
        self.assertAlmostEqual(
            comment.created_at,
            comment.updated_at,
            delta=timedelta(seconds=1)
        )
    
    def test_updated_at_changes_on_update(self):
        """Test updated_at changes when comment is updated."""
        comment = self.create_comment()
        original_updated = comment.updated_at
        
        # Wait a moment to ensure timestamp difference
        import time
        time.sleep(0.1)
        
        # Update comment
        comment.content = 'Updated content'
        comment.save()
        
        fresh_comment = self.get_fresh_comment(comment)
        self.assertGreater(fresh_comment.updated_at, original_updated)
    
    def test_created_at_does_not_change_on_update(self):
        """Test created_at remains the same when comment is updated."""
        comment = self.create_comment()
        original_created = comment.created_at
        
        # Update comment
        comment.content = 'Updated content'
        comment.save()
        
        fresh_comment = self.get_fresh_comment(comment)
        self.assertEqual(fresh_comment.created_at, original_created)


class CommentModerationTests(BaseCommentTestCase):
    """
    Test Comment moderation states (is_public, is_removed).
    """
    
    def test_comment_public_by_default(self):
        """Test comment is public by default."""
        comment = self.create_comment()
        self.assertTrue(comment.is_public)
    
    def test_comment_not_removed_by_default(self):
        """Test comment is not removed by default."""
        comment = self.create_comment()
        self.assertFalse(comment.is_removed)
    
    def test_create_comment_requiring_moderation(self):
        """Test creating comment that requires moderation."""
        comment = self.create_comment(is_public=False)
        
        self.assertFalse(comment.is_public)
        self.assertFalse(comment.is_removed)
    
    def test_mark_comment_as_removed(self):
        """Test marking comment as removed."""
        comment = self.create_comment()
        
        comment.is_removed = True
        comment.save()
        
        fresh_comment = self.get_fresh_comment(comment)
        self.assertTrue(fresh_comment.is_removed)
    
    def test_approve_moderated_comment(self):
        """Test approving a moderated comment."""
        comment = self.create_comment(is_public=False)
        
        comment.is_public = True
        comment.save()
        
        fresh_comment = self.get_fresh_comment(comment)
        self.assertTrue(fresh_comment.is_public)
    
    def test_removed_comment_can_be_public(self):
        """Test that removed comment can still be marked public (for audit)."""
        comment = self.create_comment(
            is_public=True,
            is_removed=True
        )
        
        self.assertTrue(comment.is_public)
        self.assertTrue(comment.is_removed)


class CommentEdgeCaseTests(BaseCommentTestCase):
    """
    Test edge cases and boundary conditions.
    """
    
    def test_comment_with_unicode_content(self):
        """Test comment with Unicode characters."""
        unicode_content = 'Comment with émojis 🎉 and spëcial çharacters'
        comment = self.create_comment(content=unicode_content)
        
        self.assertEqual(comment.content, unicode_content)
    
    def test_comment_with_long_valid_content(self):
        """Test comment with long but valid content."""
        long_content = 'Valid content. ' * 100  # ~1500 characters
        comment = self.create_comment(content=long_content)
        
        self.assertCommentValid(comment)
        self.assertEqual(comment.content, long_content)
    
    def test_comment_with_html_content(self):
        """Test comment containing HTML (should be stored as-is)."""
        html_content = '<p>This is <strong>HTML</strong> content</p>'
        comment = self.create_comment(content=html_content)
        
        # Should be stored as-is (sanitization happens elsewhere)
        self.assertEqual(comment.content, html_content)
    
    def test_comment_with_markdown_content(self):
        """Test comment containing Markdown."""
        markdown_content = '# Header\n\n**Bold** and *italic* text'
        comment = self.create_comment(content=markdown_content)
        
        self.assertEqual(comment.content, markdown_content)
    
    def test_comment_with_newlines_and_tabs(self):
        """Test comment with newlines and tab characters."""
        content_with_whitespace = 'Line 1\nLine 2\n\tIndented line'
        comment = self.create_comment(content=content_with_whitespace)
        
        self.assertEqual(comment.content, content_with_whitespace)
    
    def test_comment_with_special_characters(self):
        """Test comment with various special characters."""
        special_content = 'Test with $pecial ch@racters: !@#$%^&*()_+-=[]{}|;:,.<>?'
        comment = self.create_comment(content=special_content)
        
        self.assertEqual(comment.content, special_content)
    
    def test_multiple_comments_same_object(self):
        """Test multiple comments on same object."""
        comment1 = self.create_comment(content='First comment')
        comment2 = self.create_comment(content='Second comment')
        comment3 = self.create_comment(content='Third comment')
        
        # All should reference same object
        self.assertEqual(comment1.content_object, self.test_obj)
        self.assertEqual(comment2.content_object, self.test_obj)
        self.assertEqual(comment3.content_object, self.test_obj)
        
        # But have different UUIDs
        self.assertNotEqual(comment1.pk, comment2.pk)
        self.assertNotEqual(comment2.pk, comment3.pk)
    
    def test_comment_on_non_existent_object(self):
        """Test commenting on non-existent object still saves."""
        fake_uuid = str(uuid.uuid4())
        
        comment = self.Comment.objects.create(
            content_type=self.content_type,
            object_id=fake_uuid,
            user=self.regular_user,
            content='Comment on non-existent object'
        )
        
        # Should save (no FK constraint on generic relation)
        self.assertCommentValid(comment)
        self.assertIsNone(comment.content_object)


class CommentQuerySetTests(BaseCommentTestCase):
    """
    Test Comment queryset methods and manager methods.
    """
    
    def test_filter_comments_by_user(self):
        """Test filtering comments by user."""
        user1_comment = self.create_comment(user=self.regular_user)
        user2_comment = self.create_comment(user=self.another_user)
        
        user1_comments = self.Comment.objects.filter(user=self.regular_user)
        
        self.assertIn(user1_comment, user1_comments)
        self.assertNotIn(user2_comment, user1_comments)
    
    def test_filter_public_comments(self):
        """Test filtering only public comments."""
        public_comment = self.create_comment(is_public=True)
        private_comment = self.create_comment(is_public=False)
        
        public_comments = self.Comment.objects.filter(is_public=True)
        
        self.assertIn(public_comment, public_comments)
        self.assertNotIn(private_comment, public_comments)
    
    def test_filter_removed_comments(self):
        """Test filtering removed comments."""
        normal_comment = self.create_comment(is_removed=False)
        removed_comment = self.create_comment(is_removed=True)
        
        removed_comments = self.Comment.objects.filter(is_removed=True)
        
        self.assertIn(removed_comment, removed_comments)
        self.assertNotIn(normal_comment, removed_comments)
    
    def test_for_model_filters_by_content_type(self):
        """Test for_model queryset method filters by content type."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user_comment = self.create_comment()  # On User model
        
        # Create comment on different model (Comment itself)
        comment_on_comment = self.Comment.objects.create(
            content_type=ContentType.objects.get_for_model(self.Comment),
            object_id=str(user_comment.pk),
            user=self.another_user,
            content='Comment on a comment'
        )
        
        user_comments = self.Comment.objects.for_model(User)
        
        self.assertIn(user_comment, user_comments)
        self.assertNotIn(comment_on_comment, user_comments)
    
    def test_order_by_created_at_descending(self):
        """Test default ordering by created_at descending."""
        import time
        
        comment1 = self.create_comment(content='First')
        time.sleep(0.01)
        comment2 = self.create_comment(content='Second')
        time.sleep(0.01)
        comment3 = self.create_comment(content='Third')
        
        comments = list(self.Comment.objects.all())
        
        # Should be in reverse chronological order
        self.assertEqual(comments[0], comment3)
        self.assertEqual(comments[1], comment2)
        self.assertEqual(comments[2], comment1)
    
    def test_select_related_optimization(self):
        """Test that select_related optimization works."""
        comment = self.create_comment()
        
        # Use select_related to optimize
        optimized = self.Comment.objects.select_related('user').get(pk=comment.pk)
        
        # Access user should not trigger additional query
        with self.assertNumQueries(0):
            _ = optimized.user.username
    
    def test_prefetch_related_children(self):
        """Test prefetch_related for children optimization."""
        parent = self.create_comment(content='Parent')
        self.create_comment(parent=parent, content='Child 1')
        self.create_comment(parent=parent, content='Child 2')
        
        # Prefetch children
        parents_with_children = self.Comment.objects.prefetch_related('children')
        parent_optimized = parents_with_children.get(pk=parent.pk)
        
        # Access children should not trigger additional queries
        with self.assertNumQueries(0):
            children = list(parent_optimized.children.all())
            self.assertEqual(len(children), 2)


class CommentPerformanceTests(BaseCommentTestCase):
    """
    Test Comment model performance and optimization.
    """
    
    def test_bulk_create_comments(self):
        """Test bulk creating multiple comments efficiently."""
        comments_data = [
            self.Comment(
                content_type=self.content_type,
                object_id=self.test_obj_id,
                user=self.regular_user,
                content=f'Bulk comment {i}'
            )
            for i in range(100)
        ]
        
        created_comments = self.Comment.objects.bulk_create(comments_data)
        
        self.assertEqual(len(created_comments), 100)
        self.assertEqual(self.Comment.objects.count(), 100)
    
    def test_query_count_for_thread(self):
        """Test number of queries needed to fetch a comment thread."""
        # Create a thread
        root = self.create_comment(content='Root')
        for i in range(5):
            self.create_comment(parent=root, content=f'Reply {i}')
        
        # Fetch with optimizations
        with self.assertNumQueries(1):
            comments = list(
                self.Comment.objects
                .select_related('user', 'parent')
                .filter(thread_id=root.thread_id)
            )
            self.assertEqual(len(comments), 6)


class CommentDeletionTests(BaseCommentTestCase):
    """
    Test Comment deletion behavior.
    """
    
    def test_delete_root_comment_cascades_to_children(self):
        """Test deleting root comment also deletes all children."""
        root = self.create_comment(content='Root')
        child1 = self.create_comment(parent=root, content='Child 1')
        child2 = self.create_comment(parent=root, content='Child 2')
        grandchild = self.create_comment(parent=child1, content='Grandchild')
        
        root.delete()
        
        # All descendants should be deleted
        self.assertEqual(self.Comment.objects.count(), 0)
    
    def test_delete_child_comment_keeps_siblings(self):
        """Test deleting one child doesn't affect siblings."""
        root = self.create_comment(content='Root')
        child1 = self.create_comment(parent=root, content='Child 1')
        child2 = self.create_comment(parent=root, content='Child 2')
        
        child1.delete()
        
        # Root and child2 should remain
        self.assertEqual(self.Comment.objects.count(), 2)
        self.assertTrue(self.Comment.objects.filter(pk=root.pk).exists())
        self.assertTrue(self.Comment.objects.filter(pk=child2.pk).exists())
    
    def test_delete_comment_with_flags_leaves_orphaned_flags(self):
        """
        Test that deleting comment leaves associated flags orphaned.
        
        Django's GenericForeignKey does NOT support automatic CASCADE deletion.
        """
        comment = self.create_comment()
        flag = self.create_flag(comment=comment)
        comment_id = str(comment.pk)
        flag_id = flag.pk
        
        # Delete the comment
        comment.delete()
        
        # Comment should be deleted
        self.assertFalse(
            self.Comment.objects.filter(pk=comment_id).exists(),
            "Comment should be deleted"
        )
        
        # Flag remains (GenericForeignKey doesn't cascade)
        self.assertTrue(
            self.CommentFlag.objects.filter(pk=flag_id).exists(),
            "Flag should remain after comment deletion (GenericFK behavior)"
        )
        
        # Verify flag still references the deleted comment ID
        orphaned_flag = self.CommentFlag.objects.get(pk=flag_id)
        self.assertEqual(orphaned_flag.comment_id, comment_id)



class CommentUnicodeAndInternationalizationTests(BaseCommentTestCase):
    """
    Test Comment with various languages and character sets.
    """
    
    def test_comment_with_chinese_characters(self):
        """Test comment with Chinese characters."""
        chinese_content = '这是一条中文评论'
        comment = self.create_comment(content=chinese_content)
        
        self.assertEqual(comment.content, chinese_content)
    
    def test_comment_with_arabic_characters(self):
        """Test comment with Arabic characters."""
        arabic_content = 'هذا تعليق باللغة العربية'
        comment = self.create_comment(content=arabic_content)
        
        self.assertEqual(comment.content, arabic_content)
    
    def test_comment_with_russian_characters(self):
        """Test comment with Russian characters."""
        russian_content = 'Это комментарий на русском языке'
        comment = self.create_comment(content=russian_content)
        
        self.assertEqual(comment.content, russian_content)
    
    def test_comment_with_emoji(self):
        """Test comment with emoji characters."""
        emoji_content = 'Great post! 👍 😊 🎉'
        comment = self.create_comment(content=emoji_content)
        
        self.assertEqual(comment.content, emoji_content)
    
    def test_comment_with_mixed_languages(self):
        """Test comment with mixed languages."""
        mixed_content = 'Hello مرحبا 你好 Привет'
        comment = self.create_comment(content=mixed_content)
        
        self.assertEqual(comment.content, mixed_content)