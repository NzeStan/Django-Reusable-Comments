"""
Comprehensive tests for django_comments/cache.py

Tests cover all caching functionality with success, failure, and edge cases.
Uses self.test_obj (from BaseCommentTestCase) as the object being commented on.
"""

import uuid
from django.test import TestCase, override_settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import signals
from django.db import transaction
from unittest.mock import Mock, patch
from datetime import timedelta

from django_comments.tests.base import BaseCommentTestCase
from django_comments.cache import (
    get_cache_key,
    get_comment_count_cache_key,
    get_public_comment_count_cache_key,
    get_comment_count_for_object,
    get_comment_counts_for_objects,
    invalidate_comment_cache,
    invalidate_comment_cache_by_comment,
    warm_comment_cache_for_queryset,
    get_or_set_cache,
    get_comment_count_for_template,
    CACHE_TIMEOUT,
)
from django_comments.conf import comments_settings

User = get_user_model()


class CacheTestMixin:
    """Mixin for cache testing with proper cleanup."""
    
    def setUp(self):
        super().setUp()
        cache.clear()
        self._signal_handlers_connected = True
    
    def tearDown(self):
        cache.clear()
        super().tearDown()
    
    def disconnect_cache_signals(self):
        """Disconnect post_save and post_delete signals for Comment model."""
        from django_comments.cache import invalidate_cache_on_save, invalidate_cache_on_delete
        
        signals.post_save.disconnect(invalidate_cache_on_save, sender=self.Comment)
        signals.post_delete.disconnect(invalidate_cache_on_delete, sender=self.Comment)
        self._signal_handlers_connected = False
    
    def reconnect_cache_signals(self):
        """Reconnect post_save and post_delete signals for Comment model."""
        from django_comments.cache import invalidate_cache_on_save, invalidate_cache_on_delete
        
        if not self._signal_handlers_connected:
            signals.post_save.connect(invalidate_cache_on_save, sender=self.Comment)
            signals.post_delete.connect(invalidate_cache_on_delete, sender=self.Comment)
            self._signal_handlers_connected = True


# Cache Key Generation Tests
class CacheKeyGenerationTests(CacheTestMixin, BaseCommentTestCase):
    """Test cache key generation functions."""
    
    def test_get_cache_key_basic(self):
        """Test basic cache key generation."""
        key = get_cache_key('count', 'app.model', '123')
        
        self.assertIsInstance(key, str)
        self.assertIn('django_comments', key)
        self.assertIn('count', key)
    
    def test_get_cache_key_sanitizes_colons(self):
        """Test that cache keys sanitize colons to prevent key collisions."""
        key = get_cache_key('count', 'app:model', 'obj:123')
        
        parts = key.split(':')
        self.assertEqual(parts[0], 'django_comments')
        self.assertEqual(parts[1], 'count')
    
    def test_get_comment_count_cache_key(self):
        """Test get_comment_count_cache_key generates correct key."""
        key = get_comment_count_cache_key(self.test_obj)
        
        self.assertIsInstance(key, str)
        self.assertIn('django_comments', key)
        self.assertIn('count', key)
    
    def test_cache_keys_are_consistent(self):
        """Test that cache keys are consistent for the same input."""
        key1 = get_comment_count_cache_key(self.test_obj)
        key2 = get_comment_count_cache_key(self.test_obj)
        
        self.assertEqual(key1, key2)


# Single Object Caching Tests
class SingleObjectCachingTests(CacheTestMixin, BaseCommentTestCase):
    """Test get_comment_count_for_object function."""
    
    def test_get_comment_count_cache_miss(self):
        """Test getting comment count when not in cache (cache miss)."""
        comment1 = self.create_comment(content="Comment 1")
        comment2 = self.create_comment(content="Comment 2")
        
        cache.clear()
        
        count = get_comment_count_for_object(self.test_obj, public_only=False)
        
        self.assertEqual(count, 2)
        
        # Verify it's now in cache
        cache_key = get_comment_count_cache_key(self.test_obj)
        cached_value = cache.get(cache_key)
        self.assertEqual(cached_value, 2)
    
    def test_get_comment_count_cache_hit(self):
        """Test getting comment count when already in cache (cache hit)."""
        cache_key = get_comment_count_cache_key(self.test_obj)
        cache.set(cache_key, 42, CACHE_TIMEOUT)
        
        with self.assertNumQueries(0):
            count = get_comment_count_for_object(self.test_obj, public_only=False)
        
        self.assertEqual(count, 42)
    
    def test_get_public_comment_count_only_public(self):
        """Test that public_only=True filters correctly."""
        public1 = self.create_comment(content="Public 1", is_public=True)
        public2 = self.create_comment(content="Public 2", is_public=True)
        non_public = self.create_comment(content="Not public", is_public=False)
        removed = self.create_comment(content="Removed", is_public=True, is_removed=True)
        
        cache.clear()
        
        public_count = get_comment_count_for_object(self.test_obj, public_only=True)
        
        self.assertEqual(public_count, 2)
    
    def test_get_comment_count_zero_comments(self):
        """Test getting count for object with zero comments."""
        cache.clear()
        
        count = get_comment_count_for_object(self.test_obj, public_only=False)
        
        self.assertEqual(count, 0)


# Batch Object Caching Tests
class BatchObjectCachingTests(CacheTestMixin, BaseCommentTestCase):
    """Test get_comment_counts_for_objects function."""
    
    def test_get_comment_counts_all_cache_miss(self):
        """Test batch getting counts when none are in cache."""
        # Create multiple users to comment on
        users = [User.objects.create_user(username=f'user{i}', email=f'user{i}@test.com') 
                 for i in range(3)]
        
        # Add comments
        self.create_comment(content="U0C1", content_type=ContentType.objects.get_for_model(User), object_id=users[0].pk)
        self.create_comment(content="U0C2", content_type=ContentType.objects.get_for_model(User), object_id=users[0].pk)
        self.create_comment(content="U1C1", content_type=ContentType.objects.get_for_model(User), object_id=users[1].pk)
        
        cache.clear()
        
        object_ids = [u.pk for u in users]
        counts = get_comment_counts_for_objects(User, object_ids, public_only=False)
        
        self.assertEqual(counts[users[0].pk], 2)
        self.assertEqual(counts[users[1].pk], 1)
        self.assertEqual(counts[users[2].pk], 0)
    
    def test_get_comment_counts_empty_list(self):
        """Test batch getting counts with empty object_ids list."""
        counts = get_comment_counts_for_objects(User, [], public_only=False)
        
        self.assertEqual(counts, {})
    
    def test_get_comment_counts_public_only(self):
        """Test batch getting public comment counts."""
        users = [User.objects.create_user(username=f'batchuser{i}', email=f'batchuser{i}@test.com') 
                 for i in range(2)]
        
        ct = ContentType.objects.get_for_model(User)
        
        # User 0: 2 public, 1 private
        self.create_comment(content="Public 1", content_type=ct, object_id=users[0].pk, is_public=True)
        self.create_comment(content="Public 2", content_type=ct, object_id=users[0].pk, is_public=True)
        self.create_comment(content="Private", content_type=ct, object_id=users[0].pk, is_public=False)
        
        cache.clear()
        
        object_ids = [u.pk for u in users]
        counts = get_comment_counts_for_objects(User, object_ids, public_only=True)
        
        self.assertEqual(counts[users[0].pk], 2)
        self.assertEqual(counts[users[1].pk], 0)


# Cache Invalidation Tests
class CacheInvalidationTests(CacheTestMixin, BaseCommentTestCase):
    """Test cache invalidation functions."""
    
    def test_invalidate_comment_cache(self):
        """Test manual cache invalidation for an object."""
        count_key = get_comment_count_cache_key(self.test_obj)
        public_count_key = get_public_comment_count_cache_key(self.test_obj)
        
        cache.set(count_key, 10, CACHE_TIMEOUT)
        cache.set(public_count_key, 5, CACHE_TIMEOUT)
        
        invalidate_comment_cache(self.test_obj)
        
        self.assertIsNone(cache.get(count_key))
        self.assertIsNone(cache.get(public_count_key))
    
    def test_invalidate_comment_cache_by_comment_with_content_object(self):
        """Test invalidating cache by comment when content_object exists."""
        comment = self.create_comment(content="Test")
        
        count_key = get_comment_count_cache_key(self.test_obj)
        cache.set(count_key, 10, CACHE_TIMEOUT)
        
        invalidate_comment_cache_by_comment(comment)
        
        self.assertIsNone(cache.get(count_key))
    
    def test_invalidate_cache_idempotent(self):
        """Test that invalidating non-existent cache is safe (idempotent)."""
        cache.clear()
        
        try:
            invalidate_comment_cache(self.test_obj)
        except Exception as e:
            self.fail(f"Cache invalidation raised exception: {e}")


# Signal-Based Cache Invalidation Tests
class SignalCacheInvalidationTests(CacheTestMixin, BaseCommentTestCase):
    """Test automatic cache invalidation via signals."""
    
    def setUp(self):
        super().setUp()
        self.reconnect_cache_signals()
    
    def test_cache_invalidated_on_comment_create(self):
        """Test that cache is invalidated when a comment is created."""
        count = get_comment_count_for_object(self.test_obj, public_only=False)
        self.assertEqual(count, 0)
        
        cache_key = get_comment_count_cache_key(self.test_obj)
        self.assertIsNotNone(cache.get(cache_key))
        
        comment = self.create_comment(content="New comment")
        
        self.assertIsNone(cache.get(cache_key))
    
    def test_cache_invalidated_on_comment_delete(self):
        """Test that cache is invalidated when a comment is deleted."""
        comment = self.create_comment(content="Will be deleted")
        
        count = get_comment_count_for_object(self.test_obj, public_only=False)
        self.assertEqual(count, 1)
        
        cache_key = get_comment_count_cache_key(self.test_obj)
        self.assertIsNotNone(cache.get(cache_key))
        
        comment.delete()
        
        self.assertIsNone(cache.get(cache_key))


# Cache Warming Tests
class CacheWarmingTests(CacheTestMixin, BaseCommentTestCase):
    """Test warm_comment_cache_for_queryset function."""
    
    def test_warm_cache_for_queryset(self):
        """Test warming cache for a queryset of objects."""
        users = [User.objects.create_user(username=f'warmuser{i}', email=f'warmuser{i}@test.com') 
                 for i in range(3)]
        
        ct = ContentType.objects.get_for_model(User)
        for i, user in enumerate(users):
            for j in range(i + 1):
                self.create_comment(content=f"Comment {j}", content_type=ct, object_id=user.pk)
        
        cache.clear()
        
        queryset = User.objects.filter(pk__in=[u.pk for u in users])
        warm_comment_cache_for_queryset(queryset)
        
        # Verify counts are cached
        for i, user in enumerate(users):
            count_key = get_cache_key('count', f"{ct.app_label}.{ct.model}", user.pk)
            self.assertEqual(cache.get(count_key), i + 1)
    
    def test_warm_cache_empty_queryset(self):
        """Test warming cache with empty queryset."""
        queryset = User.objects.none()
        
        try:
            warm_comment_cache_for_queryset(queryset)
        except Exception as e:
            self.fail(f"Cache warming raised exception: {e}")


# Generic Cache Helper Tests
class GenericCacheHelperTests(CacheTestMixin, BaseCommentTestCase):
    """Test generic cache helper functions."""
    
    def test_get_or_set_cache_cache_miss(self):
        """Test get_or_set_cache with cache miss."""
        cache.clear()
        
        call_count = [0]
        def compute_value():
            call_count[0] += 1
            return 42
        
        value = get_or_set_cache('test_key', compute_value, timeout=CACHE_TIMEOUT)
        
        self.assertEqual(value, 42)
        self.assertEqual(call_count[0], 1)
        self.assertEqual(cache.get('test_key'), 42)
    
    def test_get_or_set_cache_cache_hit(self):
        """Test get_or_set_cache with cache hit."""
        cache.set('test_key', 99, CACHE_TIMEOUT)
        
        call_count = [0]
        def compute_value():
            call_count[0] += 1
            return 42
        
        value = get_or_set_cache('test_key', compute_value, timeout=CACHE_TIMEOUT)
        
        self.assertEqual(value, 99)
        self.assertEqual(call_count[0], 0)
    
    def test_get_comment_count_for_template(self):
        """Test template helper function."""
        self.create_comment(content="Public 1", is_public=True)
        self.create_comment(content="Public 2", is_public=True)
        self.create_comment(content="Private", is_public=False)
        
        cache.clear()
        
        count = get_comment_count_for_template(self.test_obj)
        
        self.assertEqual(count, 2)


# Edge Cases Tests
class CacheEdgeCasesTests(CacheTestMixin, BaseCommentTestCase):
    """Test edge cases and boundary conditions for cache module."""
    
    def test_cache_with_unicode_content(self):
        """Test caching with Unicode in comments."""
        emoji_comment = "Great post! 😀👍🎉💯"
        self.create_comment(content=emoji_comment)
        
        cache.clear()
        
        count = get_comment_count_for_object(self.test_obj, public_only=False)
        
        self.assertEqual(count, 1)
    
    def test_cache_after_bulk_create(self):
        """Test cache behavior after bulk_create (signals don't fire)."""
        count = get_comment_count_for_object(self.test_obj, public_only=False)
        self.assertEqual(count, 0)
        
        cache_key = get_comment_count_cache_key(self.test_obj)
        self.assertIsNotNone(cache.get(cache_key))
        
        # Bulk create comments (signals won't fire)
        ct = ContentType.objects.get_for_model(self.test_obj.__class__)
        comments = [
            self.Comment(
                content_type=ct,
                object_id=self.test_obj.pk,
                user=self.regular_user,
                content=f"Comment {i}"
            )
            for i in range(5)
        ]
        self.Comment.objects.bulk_create(comments)
        
        # Cache should still be there (not invalidated)
        cached_value = cache.get(cache_key)
        self.assertIsNotNone(cached_value)
        self.assertEqual(cached_value, 0)  # Stale cache
        
        # Manual invalidation needed
        invalidate_comment_cache(self.test_obj)
        self.assertIsNone(cache.get(cache_key))
    
    def test_cache_key_collision_resistance(self):
        """Test that similar inputs don't cause key collisions."""
        user1 = self.regular_user
        user2 = self.another_user
        
        key1 = get_comment_count_cache_key(user1)
        key2 = get_comment_count_cache_key(user2)
        
        self.assertNotEqual(key1, key2)
        
        cache.set(key1, 10, CACHE_TIMEOUT)
        cache.set(key2, 20, CACHE_TIMEOUT)
        
        self.assertEqual(cache.get(key1), 10)
        self.assertEqual(cache.get(key2), 20)


# Real-World Scenario Tests
class RealWorldCacheScenarioTests(CacheTestMixin, BaseCommentTestCase):
    """Test real-world usage scenarios for cache module."""
    
    def test_comment_moderation_scenario(self):
        """Test cache behavior during comment moderation."""
        comment1 = self.create_comment(content="Comment 1", is_public=True)
        comment2 = self.create_comment(content="Comment 2", is_public=False)
        comment3 = self.create_comment(content="Comment 3", is_public=True)
        
        cache.clear()
        public_count = get_comment_count_for_object(self.test_obj, public_only=True)
        self.assertEqual(public_count, 2)
        
        # Moderate comment1 (make it non-public)
        comment1.is_public = False
        comment1.save()
        
        # Cache should be invalidated
        cache_key = get_public_comment_count_cache_key(self.test_obj)
        self.assertIsNone(cache.get(cache_key))
        
        # Re-query should show updated count
        public_count = get_comment_count_for_object(self.test_obj, public_only=True)
        self.assertEqual(public_count, 1)
    
    def test_high_traffic_scenario(self):
        """Test cache behavior under high traffic simulation."""
        for i in range(10):
            self.create_comment(content=f"Comment {i}")
        
        cache.clear()
        
        # Simulate many read requests
        for _ in range(20):
            count = get_comment_count_for_object(self.test_obj, public_only=True)
            self.assertEqual(count, 10)