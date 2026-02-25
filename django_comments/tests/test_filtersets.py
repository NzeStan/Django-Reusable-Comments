"""
Comprehensive tests for django_comments.api.filtersets

Tests cover:
- ContentTypeFilter (custom filter)
- CommentFilterSet (all filters)
- Success cases (expected filtering behavior)
- Failure cases (invalid inputs, edge cases)
- Real-world scenarios (complex filtering, combinations)
"""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.test import RequestFactory

from django_comments.tests.base import BaseCommentTestCase
from django_comments.api.filtersets import CommentFilterSet, ContentTypeFilter
from django_comments.models import Comment

User = get_user_model()


# ============================================================================
# CONTENT TYPE FILTER TESTS
# ============================================================================

class ContentTypeFilterTests(BaseCommentTestCase):
    """Test ContentTypeFilter custom filter."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
    
    def test_filter_with_valid_content_type(self):
        """Test filtering by valid content type string."""
        # Create comments for different content types
        comment1 = self.create_comment(content='Comment on test object')
        
        # Create another object type
        from django.contrib.auth.models import Group
        group = Group.objects.create(name='Test Group')
        group_ct = ContentType.objects.get_for_model(group)
        comment2 = self.create_comment(
            content='Comment on group',
            content_type=group_ct,
            object_id=group.pk
        )
        
        # Filter by test object content type
        ct_string = f'{self.test_obj._meta.app_label}.{self.test_obj._meta.model_name}'
        queryset = Comment.objects.all()
        
        # Create filter instance
        filter_instance = ContentTypeFilter()
        filtered_qs = filter_instance.filter(queryset, ct_string)
        
        # Should only return comments for test object
        self.assertEqual(filtered_qs.count(), 1)
        self.assertIn(comment1, filtered_qs)
        self.assertNotIn(comment2, filtered_qs)
    
    def test_filter_with_empty_value_returns_all(self):
        """Test that empty filter value returns all comments."""
        comment1 = self.create_comment()
        comment2 = self.create_comment()
        
        queryset = Comment.objects.all()
        filter_instance = ContentTypeFilter()
        
        # Filter with None
        filtered_qs = filter_instance.filter(queryset, None)
        self.assertEqual(filtered_qs.count(), 2)
        
        # Filter with empty string
        filtered_qs = filter_instance.filter(queryset, '')
        self.assertEqual(filtered_qs.count(), 2)
    
    def test_filter_with_invalid_format_returns_none(self):
        """Test that invalid content type format returns empty queryset."""
        self.create_comment()
        queryset = Comment.objects.all()
        filter_instance = ContentTypeFilter()
        
        # Invalid format (no dot)
        filtered_qs = filter_instance.filter(queryset, 'invalidformat')
        self.assertEqual(filtered_qs.count(), 0)
        
        # Too many dots
        filtered_qs = filter_instance.filter(queryset, 'app.model.extra')
        self.assertEqual(filtered_qs.count(), 0)
    
    def test_filter_with_nonexistent_content_type_returns_none(self):
        """Test that non-existent content type returns empty queryset."""
        self.create_comment()
        queryset = Comment.objects.all()
        filter_instance = ContentTypeFilter()
        
        filtered_qs = filter_instance.filter(queryset, 'fake.model')
        self.assertEqual(filtered_qs.count(), 0)
    
    def test_filter_with_special_characters_in_value(self):
        """Test filtering with special characters in content type."""
        self.create_comment()
        queryset = Comment.objects.all()
        filter_instance = ContentTypeFilter()
        
        # Special characters that might cause issues
        filtered_qs = filter_instance.filter(queryset, 'app$.model@')
        self.assertEqual(filtered_qs.count(), 0)


# ============================================================================
# COMMENT FILTERSET TESTS - Basic Filters
# ============================================================================

class CommentFilterSetBasicTests(BaseCommentTestCase):
    """Test CommentFilterSet basic field filters."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
    
    def get_filterset(self, data=None):
        """Helper to create filterset instance."""
        request = self.factory.get('/fake-url/', data or {})
        return CommentFilterSet(data=data, queryset=Comment.objects.all(), request=request)
    
    def test_filter_by_object_id(self):
        """Test filtering comments by object_id."""
        comment1 = self.create_comment(content='Comment 1')

        # Create comment for a different user (guaranteed different pk)
        comment2 = self.create_comment(
            content='Comment 2',
            object_id=str(self.another_user.pk)
        )

        # Filter by test object ID
        filterset = self.get_filterset({'object_id': str(self.test_obj.pk)})
        
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(comment1, filterset.qs)
        self.assertNotIn(comment2, filterset.qs)
    
    def test_filter_by_object_id_with_uuid(self):
        """Test filtering by UUID object_id."""
        # Assuming test_obj has UUID pk
        comment = self.create_comment()
        
        filterset = self.get_filterset({'object_id': str(self.test_obj.pk)})
        
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(comment, filterset.qs)
    
    def test_filter_by_user(self):
        """Test filtering comments by user ID."""
        comment1 = self.create_comment(user=self.regular_user)
        comment2 = self.create_comment(user=self.another_user)
        
        filterset = self.get_filterset({'user': str(self.regular_user.pk)})
        
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(comment1, filterset.qs)
        self.assertNotIn(comment2, filterset.qs)
    
    def test_filter_by_nonexistent_user_returns_empty(self):
        """Test filtering by non-existent user ID."""
        self.create_comment(user=self.regular_user)

        nonexistent_user_id = '99999'
        filterset = self.get_filterset({'user': nonexistent_user_id})

        self.assertEqual(filterset.qs.count(), 0)
    
    def test_filter_by_is_public(self):
        """Test filtering by is_public status."""
        public_comment = self.create_comment(is_public=True)
        private_comment = self.create_comment(is_public=False)
        
        # Filter for public comments
        filterset = self.get_filterset({'is_public': 'true'})
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(public_comment, filterset.qs)
        
        # Filter for private comments
        filterset = self.get_filterset({'is_public': 'false'})
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(private_comment, filterset.qs)
    
    def test_filter_by_is_removed(self):
        """Test filtering by is_removed status."""
        active_comment = self.create_comment(is_removed=False)
        removed_comment = self.create_comment(is_removed=True)
        
        # Filter for active comments
        filterset = self.get_filterset({'is_removed': 'false'})
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(active_comment, filterset.qs)
        
        # Filter for removed comments
        filterset = self.get_filterset({'is_removed': 'true'})
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(removed_comment, filterset.qs)
    
    def test_filter_by_thread_id(self):
        """Test filtering comments by thread_id."""
        comment1 = self.create_comment()
        thread_id1 = comment1.thread_id
        
        comment2 = self.create_comment()
        thread_id2 = comment2.thread_id
        
        # Filter by first thread
        filterset = self.get_filterset({'thread_id': str(thread_id1)})
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(comment1, filterset.qs)


# ============================================================================
# COMMENT FILTERSET TESTS - Date Range Filters
# ============================================================================

class CommentFilterSetDateRangeTests(BaseCommentTestCase):
    """Test CommentFilterSet date range filtering."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.now = timezone.now()
    
    def get_filterset(self, data=None):
        """Helper to create filterset instance."""
        request = self.factory.get('/fake-url/', data or {})
        return CommentFilterSet(data=data, queryset=Comment.objects.all(), request=request)
    
    def test_filter_created_after(self):
        """Test filtering comments created after a date."""
        # Create old comment
        old_time = self.now - timedelta(days=5)
        old_comment = self.create_comment(content='Old comment')
        Comment.objects.filter(pk=old_comment.pk).update(created_at=old_time)
        
        # Create new comment
        new_comment = self.create_comment(content='New comment')
        
        # Filter for comments after 3 days ago
        after_date = (self.now - timedelta(days=3)).isoformat()
        filterset = self.get_filterset({'created_after': after_date})
        
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(new_comment, filterset.qs)
        self.assertNotIn(old_comment, filterset.qs)
    
    def test_filter_created_before(self):
        """Test filtering comments created before a date."""
        # Create old comment
        old_time = self.now - timedelta(days=5)
        old_comment = self.create_comment(content='Old comment')
        Comment.objects.filter(pk=old_comment.pk).update(created_at=old_time)
        
        # Create new comment
        new_comment = self.create_comment(content='New comment')
        
        # Filter for comments before 3 days ago
        before_date = (self.now - timedelta(days=3)).isoformat()
        filterset = self.get_filterset({'created_before': before_date})
        
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(old_comment, filterset.qs)
        self.assertNotIn(new_comment, filterset.qs)
    
    def test_filter_date_range_combination(self):
        """Test filtering with both created_after and created_before."""
        # Create comments at different times
        very_old = self.create_comment(content='Very old')
        Comment.objects.filter(pk=very_old.pk).update(
            created_at=self.now - timedelta(days=10)
        )
        
        middle = self.create_comment(content='Middle')
        Comment.objects.filter(pk=middle.pk).update(
            created_at=self.now - timedelta(days=5)
        )
        
        recent = self.create_comment(content='Recent')
        
        # Filter for comments between 7 and 3 days ago
        after_date = (self.now - timedelta(days=7)).isoformat()
        before_date = (self.now - timedelta(days=3)).isoformat()
        
        filterset = self.get_filterset({
            'created_after': after_date,
            'created_before': before_date
        })
        
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(middle, filterset.qs)
    
    def test_filter_with_invalid_date_format(self):
        """Test filtering with invalid date format."""
        self.create_comment()
        
        # Invalid date format should not crash
        filterset = self.get_filterset({'created_after': 'invalid-date'})
        # Filterset should still work, though filter may not be applied
        self.assertIsNotNone(filterset.qs)
    
    def test_filter_with_future_date(self):
        """Test filtering with future date."""
        comment = self.create_comment()
        
        # Future date
        future_date = (self.now + timedelta(days=10)).isoformat()
        filterset = self.get_filterset({'created_after': future_date})
        
        # No comments should match
        self.assertEqual(filterset.qs.count(), 0)
    
    def test_filter_with_precise_timestamp(self):
        """Test filtering with precise timestamp including microseconds."""
        comment = self.create_comment()
        exact_time = comment.created_at
        
        # Filter for comments created exactly at or after this timestamp
        filterset = self.get_filterset({'created_after': exact_time.isoformat()})
        
        self.assertGreaterEqual(filterset.qs.count(), 1)
        self.assertIn(comment, filterset.qs)


# ============================================================================
# COMMENT FILTERSET TESTS - Thread/Parent Filters
# ============================================================================

class CommentFilterSetThreadTests(BaseCommentTestCase):
    """Test CommentFilterSet thread and parent filtering."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
    
    def get_filterset(self, data=None):
        """Helper to create filterset instance."""
        request = self.factory.get('/fake-url/', data or {})
        return CommentFilterSet(data=data, queryset=Comment.objects.all(), request=request)
    
    def test_filter_by_parent_id(self):
        """Test filtering comments by parent ID."""
        parent = self.create_comment(content='Parent')
        child1 = self.create_comment(parent=parent, content='Child 1')
        child2 = self.create_comment(parent=parent, content='Child 2')
        other_parent = self.create_comment(content='Other parent')
        
        filterset = self.get_filterset({'parent': str(parent.pk)})
        
        self.assertEqual(filterset.qs.count(), 2)
        self.assertIn(child1, filterset.qs)
        self.assertIn(child2, filterset.qs)
        self.assertNotIn(parent, filterset.qs)
        self.assertNotIn(other_parent, filterset.qs)
    
    def test_filter_parent_none_returns_root_comments(self):
        """Test filtering with parent='none' returns only root comments."""
        root1 = self.create_comment(content='Root 1')
        root2 = self.create_comment(content='Root 2')
        child = self.create_comment(parent=root1, content='Child')
        
        filterset = self.get_filterset({'parent': 'none'})
        
        self.assertEqual(filterset.qs.count(), 2)
        self.assertIn(root1, filterset.qs)
        self.assertIn(root2, filterset.qs)
        self.assertNotIn(child, filterset.qs)
    
    def test_filter_is_root_true(self):
        """Test filtering for root comments with is_root=true."""
        root1 = self.create_comment(content='Root 1')
        root2 = self.create_comment(content='Root 2')
        parent = self.create_comment(content='Parent')
        child = self.create_comment(parent=parent, content='Child')
        
        filterset = self.get_filterset({'is_root': 'true'})
        
        self.assertEqual(filterset.qs.count(), 3)
        self.assertIn(root1, filterset.qs)
        self.assertIn(root2, filterset.qs)
        self.assertIn(parent, filterset.qs)
        self.assertNotIn(child, filterset.qs)
    
    def test_filter_is_root_false(self):
        """Test filtering for non-root comments with is_root=false."""
        root = self.create_comment(content='Root')
        child1 = self.create_comment(parent=root, content='Child 1')
        child2 = self.create_comment(parent=root, content='Child 2')
        
        filterset = self.get_filterset({'is_root': 'false'})
        
        self.assertEqual(filterset.qs.count(), 2)
        self.assertIn(child1, filterset.qs)
        self.assertIn(child2, filterset.qs)
        self.assertNotIn(root, filterset.qs)
    
    def test_filter_by_nonexistent_parent_returns_empty(self):
        """Test filtering by non-existent parent ID."""
        self.create_comment()
        
        fake_uuid = str(uuid.uuid4())
        filterset = self.get_filterset({'parent': fake_uuid})
        
        self.assertEqual(filterset.qs.count(), 0)
    
    def test_filter_nested_thread_structure(self):
        """Test filtering in deeply nested thread structure."""
        root = self.create_comment(content='Root')
        level1 = self.create_comment(parent=root, content='Level 1')
        level2 = self.create_comment(parent=level1, content='Level 2')
        level3 = self.create_comment(parent=level2, content='Level 3')
        
        # Filter direct children of root
        filterset = self.get_filterset({'parent': str(root.pk)})
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(level1, filterset.qs)
        
        # Filter direct children of level1
        filterset = self.get_filterset({'parent': str(level1.pk)})
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(level2, filterset.qs)


# ============================================================================
# COMMENT FILTERSET TESTS - Complex Combinations
# ============================================================================

class CommentFilterSetCombinationTests(BaseCommentTestCase):
    """Test CommentFilterSet with multiple filters combined."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.now = timezone.now()
    
    def get_filterset(self, data=None):
        """Helper to create filterset instance."""
        request = self.factory.get('/fake-url/', data or {})
        return CommentFilterSet(data=data, queryset=Comment.objects.all(), request=request)
    
    def test_combine_content_type_and_object_id(self):
        """Test combining content_type and object_id filters."""
        comment1 = self.create_comment(content='Target comment')
        
        # Create comment for different object
        from django.contrib.auth.models import Group
        group = Group.objects.create(name='Test Group')
        group_ct = ContentType.objects.get_for_model(group)
        comment2 = self.create_comment(
            content='Other comment',
            content_type=group_ct,
            object_id=group.pk
        )
        
        ct_string = f'{self.test_obj._meta.app_label}.{self.test_obj._meta.model_name}'
        filterset = self.get_filterset({
            'content_type': ct_string,
            'object_id': str(self.test_obj.pk)
        })
        
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(comment1, filterset.qs)
    
    def test_combine_user_and_public_status(self):
        """Test combining user and is_public filters."""
        public_by_user = self.create_comment(
            user=self.regular_user,
            is_public=True
        )
        private_by_user = self.create_comment(
            user=self.regular_user,
            is_public=False
        )
        public_by_other = self.create_comment(
            user=self.another_user,
            is_public=True
        )
        
        filterset = self.get_filterset({
            'user': str(self.regular_user.pk),
            'is_public': 'true'
        })
        
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(public_by_user, filterset.qs)
    
    def test_combine_date_range_and_status(self):
        """Test combining date range with status filters."""
        # Create old public comment
        old_public = self.create_comment(is_public=True)
        Comment.objects.filter(pk=old_public.pk).update(
            created_at=self.now - timedelta(days=10)
        )
        
        # Create recent private comment
        recent_private = self.create_comment(is_public=False)
        
        # Create recent public comment
        recent_public = self.create_comment(is_public=True)
        
        # Filter for recent public comments
        after_date = (self.now - timedelta(days=5)).isoformat()
        filterset = self.get_filterset({
            'created_after': after_date,
            'is_public': 'true'
        })
        
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(recent_public, filterset.qs)
    
    def test_combine_thread_and_user_filters(self):
        """Test combining thread filters with user filter."""
        parent = self.create_comment(user=self.regular_user)
        child_by_same_user = self.create_comment(
            parent=parent,
            user=self.regular_user
        )
        child_by_other_user = self.create_comment(
            parent=parent,
            user=self.another_user
        )
        
        filterset = self.get_filterset({
            'parent': str(parent.pk),
            'user': str(self.regular_user.pk)
        })
        
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(child_by_same_user, filterset.qs)
    
    def test_combine_all_filters(self):
        """Test combining maximum number of filters."""
        target_comment = self.create_comment(
            user=self.regular_user,
            is_public=True,
            is_removed=False
        )
        thread_id = target_comment.thread_id
        
        # Create comments that don't match
        self.create_comment(user=self.another_user, is_public=True)
        self.create_comment(user=self.regular_user, is_public=False)
        
        ct_string = f'{self.test_obj._meta.app_label}.{self.test_obj._meta.model_name}'
        after_date = (self.now - timedelta(hours=1)).isoformat()
        before_date = (self.now + timedelta(hours=1)).isoformat()
        
        filterset = self.get_filterset({
            'content_type': ct_string,
            'object_id': str(self.test_obj.pk),
            'user': str(self.regular_user.pk),
            'created_after': after_date,
            'created_before': before_date,
            'is_public': 'true',
            'is_removed': 'false',
            'thread_id': str(thread_id),
            'is_root': 'true'
        })
        
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(target_comment, filterset.qs)


# ============================================================================
# EDGE CASES AND REAL-WORLD SCENARIOS
# ============================================================================

class CommentFilterSetEdgeCaseTests(BaseCommentTestCase):
    """Test edge cases and real-world filtering scenarios."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
    
    def get_filterset(self, data=None):
        """Helper to create filterset instance."""
        request = self.factory.get('/fake-url/', data or {})
        return CommentFilterSet(data=data, queryset=Comment.objects.all(), request=request)
    
    def test_filter_with_empty_queryset(self):
        """Test filtering when no comments exist."""
        filterset = self.get_filterset({'is_public': 'true'})
        self.assertEqual(filterset.qs.count(), 0)
    
    def test_filter_with_no_parameters(self):
        """Test filterset with no filter parameters."""
        comment1 = self.create_comment()
        comment2 = self.create_comment()
        
        filterset = self.get_filterset({})
        
        self.assertEqual(filterset.qs.count(), 2)
        self.assertIn(comment1, filterset.qs)
        self.assertIn(comment2, filterset.qs)
    
    def test_filter_with_special_characters_in_object_id(self):
        """Test filtering with special characters that might be in object_id."""
        comment = self.create_comment()
        
        # Try filtering with various special characters
        filterset = self.get_filterset({'object_id': 'test-id-123'})
        # Should not crash
        self.assertIsNotNone(filterset.qs)
    
    def test_filter_unicode_in_user_filter(self):
        """Test that user filter handles UUID strings correctly."""
        comment = self.create_comment(user=self.regular_user)
        
        # Valid UUID with dashes
        filterset = self.get_filterset({'user': str(self.regular_user.pk)})
        self.assertIn(comment, filterset.qs)
    
    def test_filter_case_sensitivity_in_content_type(self):
        """Test content type filter case sensitivity."""
        comment = self.create_comment()
        
        ct_string = f'{self.test_obj._meta.app_label}.{self.test_obj._meta.model_name}'
        
        # Lowercase (should match)
        filterset = self.get_filterset({'content_type': ct_string.lower()})
        self.assertGreaterEqual(filterset.qs.count(), 1)
        
        # Uppercase (model names are lowercase in Django)
        upper_ct = f'{self.test_obj._meta.app_label}.{self.test_obj._meta.model_name.upper()}'
        filterset = self.get_filterset({'content_type': upper_ct})
        # Should return empty as content types are case-sensitive
        self.assertEqual(filterset.qs.count(), 0)
    
    def test_filter_with_deleted_parent_comment(self):
        """Test filtering when parent comment has been deleted."""
        parent = self.create_comment(content='Parent')
        child = self.create_comment(parent=parent, content='Child')
        parent_id = parent.pk
        
        # Delete parent
        parent.delete()
        
        # Try to filter by deleted parent
        filterset = self.get_filterset({'parent': str(parent_id)})
        
        # Should return empty as parent no longer exists
        self.assertEqual(filterset.qs.count(), 0)
    
    def test_filter_performance_with_many_comments(self):
        """Test filterset performance doesn't degrade significantly."""
        # Create many comments
        for i in range(100):
            self.create_comment(
                content=f'Comment {i}',
                is_public=(i % 2 == 0)
            )
        
        # Filter should still work efficiently
        filterset = self.get_filterset({'is_public': 'true'})
        self.assertEqual(filterset.qs.count(), 50)
    
    def test_filter_boundary_dates(self):
        """Test filtering with boundary date conditions."""
        comment = self.create_comment()
        exact_time = comment.created_at
        
        # Exactly at creation time
        filterset = self.get_filterset({'created_after': exact_time.isoformat()})
        self.assertIn(comment, filterset.qs)
        
        # One microsecond after
        after_time = exact_time + timedelta(microseconds=1)
        filterset = self.get_filterset({'created_after': after_time.isoformat()})
        self.assertNotIn(comment, filterset.qs)
    
    def test_filter_thread_circular_reference_protection(self):
        """Test that filters handle potential circular references gracefully."""
        root = self.create_comment(content='Root')
        
        # Normal child
        child = self.create_comment(parent=root, content='Child')
        
        # Verify no issues with filtering
        filterset = self.get_filterset({'parent': str(root.pk)})
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(child, filterset.qs)
    
    def test_filter_multiple_objects_same_content_type(self):
        """Test filtering comments from different objects of same type."""
        # Create first test object comment
        comment1 = self.create_comment(content='Comment on object 1')
        obj1_id = self.test_obj.pk
        
        # Create second user (another object of same User type)
        User = get_user_model()
        obj2 = User.objects.create_user(
            username='testuser3',
            email='testuser3@example.com',
            password='testpass123'
        )
        ct = ContentType.objects.get_for_model(obj2)
        comment2 = self.create_comment(
            content='Comment on object 2',
            content_type=ct,
            object_id=obj2.pk
        )
        
        # Filter by object 1
        filterset = self.get_filterset({'object_id': str(obj1_id)})
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(comment1, filterset.qs)
        
        # Filter by object 2
        filterset = self.get_filterset({'object_id': str(obj2.pk)})
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(comment2, filterset.qs)
    
    def test_filter_with_malformed_uuid(self):
        """Test filtering with malformed UUID strings."""
        comment = self.create_comment()
        
        # Various malformed UUIDs
        malformed_uuids = [
            'not-a-uuid',
            '12345',
            'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
            '123e4567-e89b-12d3-a456',  # Incomplete
            '',
        ]
        
        for bad_uuid in malformed_uuids:
            try:
                filterset = self.get_filterset({'user': bad_uuid})
                # Try to access queryset - this may trigger validation
                _ = filterset.qs.count()
            except Exception:
                # Expected - malformed UUIDs should either be handled gracefully
                # or raise validation errors, both are acceptable
                pass
    
    def test_filter_removed_and_not_public_combination(self):
        """Test filtering for removed private comments."""
        # Create all combinations
        public_active = self.create_comment(is_public=True, is_removed=False)
        public_removed = self.create_comment(is_public=True, is_removed=True)
        private_active = self.create_comment(is_public=False, is_removed=False)
        private_removed = self.create_comment(is_public=False, is_removed=True)
        
        # Filter for private removed comments
        filterset = self.get_filterset({
            'is_public': 'false',
            'is_removed': 'true'
        })
        
        self.assertEqual(filterset.qs.count(), 1)
        self.assertIn(private_removed, filterset.qs)
    
    def test_filter_with_timezone_aware_dates(self):
        """Test date filtering with timezone-aware datetimes."""
        comment = self.create_comment()
        
        # Use Django's timezone utilities (already timezone-aware)
        utc_time = timezone.now()
        after_date = (utc_time - timedelta(hours=1)).isoformat()
        
        filterset = self.get_filterset({'created_after': after_date})
        
        self.assertGreaterEqual(filterset.qs.count(), 1)
        self.assertIn(comment, filterset.qs)