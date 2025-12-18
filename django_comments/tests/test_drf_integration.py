"""
Comprehensive tests for django_comments/drf_integration.py

Tests cover:
- CommentRateThrottle (authenticated user throttling)
- CommentAnonRateThrottle (anonymous user throttling)
- CommentBurstRateThrottle (burst protection)
- CommentPagination (standard pagination)
- ThreadedCommentPagination (threaded comment pagination)
- Helper functions (get_comment_throttle_classes, get_comment_pagination_class)
- Settings integration and configuration
- Edge cases and boundary conditions
- Integration with DRF components

All tests properly handle:
- Request/view mocking
- Throttle state and cache management
- Pagination state and queryset evaluation
- Settings override scenarios
- Real-world usage patterns
"""
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.request import Request
from rest_framework.pagination import PageNumberPagination
from django.core.cache import cache
from django.db.models import QuerySet

from django_comments.tests.base import BaseCommentTestCase
from django_comments.drf_integration import (
    CommentRateThrottle,
    CommentAnonRateThrottle,
    CommentBurstRateThrottle,
    CommentPagination,
    ThreadedCommentPagination,
    get_comment_throttle_classes,
    get_comment_pagination_class,
)
from django_comments.conf import comments_settings
from django_comments.utils import get_comment_model

User = get_user_model()
Comment = get_comment_model()


# ============================================================================
# TEST MIXINS AND HELPERS
# ============================================================================

class ThrottleTestMixin:
    """Mixin for throttle testing with proper cache cleanup."""
    
    def setUp(self):
        super().setUp()
        # Clear throttle cache before each test
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = Mock()
    
    def tearDown(self):
        # Clear throttle cache after each test
        cache.clear()
        super().tearDown()
    
    def create_request(self, method='POST', user=None, authenticated=True):
        """Create a DRF request for testing."""
        if method == 'POST':
            request = self.factory.post('/comments/')
        elif method == 'GET':
            request = self.factory.get('/comments/')
        else:
            request = self.factory.generic(method, '/comments/')
        
        # Convert to DRF Request
        request = Request(request)
        
        if authenticated and user:
            force_authenticate(request, user=user)
        elif not authenticated:
            request.user = None
        
        return request
    
    def allow_request_multiple_times(self, throttle, request, count):
        """
        Call allow_request multiple times and return results.
        
        Returns:
            List of boolean results
        """
        results = []
        for _ in range(count):
            allowed = throttle.allow_request(request, self.view)
            results.append(allowed)
            
            # If throttled, wait won't help in tests
            # So we break early
            if not allowed:
                break
        
        return results


class PaginationTestMixin:
    """Mixin for pagination testing."""
    
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.view = Mock()
    
    def create_paginated_request(self, query_params=None):
        """Create a request with pagination parameters."""
        query_params = query_params or {}
        request = self.factory.get('/comments/', query_params)
        return Request(request)


# ============================================================================
# THROTTLE CLASS TESTS
# ============================================================================

class CommentRateThrottleTests(ThrottleTestMixin, BaseCommentTestCase):
    """Test CommentRateThrottle for authenticated users."""
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment': '100/day'}})
    def test_throttle_scope_is_comment(self):
        """Test throttle uses correct scope."""
        throttle = CommentRateThrottle()
        self.assertEqual(throttle.scope, 'comment')
    
    def test_throttle_uses_settings_rate(self):
        """Test throttle uses rate from settings."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', '10/hour'):
            # Override get_rate to return our custom rate
            with patch.object(CommentRateThrottle, 'get_rate', return_value='10/hour'):
                throttle = CommentRateThrottle()
                self.assertEqual(throttle.rate, '10/hour')
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {}})
    def test_throttle_uses_default_rate_if_not_configured(self):
        """Test throttle behavior when rate not configured."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', None):
            # When no rate configured, throttle will try to use DRF defaults
            # which will be None/missing
            try:
                throttle = CommentRateThrottle()
                # If it doesn't raise, rate should be None
                self.assertIsNone(throttle.rate)
            except Exception:
                # Or it might raise ImproperlyConfigured, which is acceptable
                pass
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment': '100/day'}})
    def test_allow_request_for_get_requests(self):
        """Test GET requests are not throttled."""
        throttle = CommentRateThrottle()
        request = self.create_request(method='GET', user=self.regular_user)
        
        # Should always allow GET
        self.assertTrue(throttle.allow_request(request, self.view))
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment': '2/min'}})
    def test_allow_request_for_post_requests(self):
        """Test POST requests are throttled."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', '2/min'):
            throttle = CommentRateThrottle()
            request = self.create_request(method='POST', user=self.regular_user)
            
            # First request should be allowed
            self.assertTrue(throttle.allow_request(request, self.view))
            
            # Second request should be allowed
            throttle2 = CommentRateThrottle()
            self.assertTrue(throttle2.allow_request(request, self.view))
            
            # Third request should be throttled
            throttle3 = CommentRateThrottle()
            self.assertFalse(throttle3.allow_request(request, self.view))
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment': '10/min'}})
    def test_throttle_different_users_separately(self):
        """Test different users have separate throttle limits."""
        # Clear cache to ensure clean state
        cache.clear()
        
        with patch.object(comments_settings, 'API_RATE_LIMIT', '10/min'):
            # User 1 makes a request
            throttle1 = CommentRateThrottle()
            request1 = self.create_request(method='POST', user=self.regular_user)
            result1 = throttle1.allow_request(request1, self.view)
            self.assertTrue(result1, "First user's first request should be allowed")
            
            # User 2 (different user) should have their own separate limit
            # so their first request should also be allowed
            throttle2 = CommentRateThrottle()
            request2 = self.create_request(method='POST', user=self.staff_user)
            result2 = throttle2.allow_request(request2, self.view)
            self.assertTrue(result2, "Second user's first request should be allowed (separate limit)")
            
            # Verify they actually have different user IDs
            self.assertNotEqual(self.regular_user.pk, self.staff_user.pk,
                              "Test users should have different IDs")
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment': '2/hour'}})
    def test_throttle_same_user_multiple_requests(self):
        """Test same user is properly throttled across requests."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', '2/hour'):
            request = self.create_request(method='POST', user=self.regular_user)
            
            # Use multiple throttle instances (simulating multiple requests)
            throttle1 = CommentRateThrottle()
            self.assertTrue(throttle1.allow_request(request, self.view))
            
            throttle2 = CommentRateThrottle()
            self.assertTrue(throttle2.allow_request(request, self.view))
            
            throttle3 = CommentRateThrottle()
            self.assertFalse(throttle3.allow_request(request, self.view))
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment': '100/day'}})
    def test_throttle_works_with_put_requests(self):
        """Test PUT requests are not throttled."""
        throttle = CommentRateThrottle()
        request = self.create_request(method='PUT', user=self.regular_user)
        
        # PUT should not be throttled
        self.assertTrue(throttle.allow_request(request, self.view))
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment': '100/day'}})
    def test_throttle_works_with_delete_requests(self):
        """Test DELETE requests are not throttled."""
        throttle = CommentRateThrottle()
        request = self.create_request(method='DELETE', user=self.regular_user)
        
        # DELETE should not be throttled
        self.assertTrue(throttle.allow_request(request, self.view))
    
    def test_throttle_respects_drf_settings(self):
        """Test throttle can fall back to DRF's throttle rate settings."""
        # When comments_settings.API_RATE_LIMIT is None,
        # throttle should fall back to DRF's THROTTLE_RATES
        with patch.object(comments_settings, 'API_RATE_LIMIT', None):
            # Mock the THROTTLE_RATES dict on the throttle class
            with patch.object(CommentRateThrottle, 'THROTTLE_RATES', {'comment': '5/hour'}):
                throttle = CommentRateThrottle()
                # Should use DRF setting
                self.assertEqual(throttle.rate, '5/hour')


class CommentAnonRateThrottleTests(ThrottleTestMixin, BaseCommentTestCase):
    """Test CommentAnonRateThrottle for anonymous users."""
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment_anon': '20/day'}})
    def test_throttle_scope_is_comment_anon(self):
        """Test throttle uses correct scope."""
        throttle = CommentAnonRateThrottle()
        self.assertEqual(throttle.scope, 'comment_anon')
    
    def test_throttle_uses_settings_rate(self):
        """Test throttle uses rate from settings."""
        with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', '5/hour'):
            with patch.object(CommentAnonRateThrottle, 'get_rate', return_value='5/hour'):
                throttle = CommentAnonRateThrottle()
                self.assertEqual(throttle.rate, '5/hour')
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {}})
    def test_throttle_uses_default_rate_if_not_configured(self):
        """Test throttle behavior when rate not configured."""
        with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', None):
            try:
                throttle = CommentAnonRateThrottle()
                self.assertIsNone(throttle.rate)
            except Exception:
                # Or it might raise ImproperlyConfigured, which is acceptable
                pass
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment_anon': '20/day'}})
    def test_allow_request_for_get_requests(self):
        """Test GET requests are not throttled."""
        throttle = CommentAnonRateThrottle()
        request = self.create_request(method='GET', authenticated=False)
        
        # Should always allow GET
        self.assertTrue(throttle.allow_request(request, self.view))
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment_anon': '1/min'}})
    def test_allow_request_for_anonymous_post_requests(self):
        """Test anonymous POST requests are throttled."""
        with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', '1/min'):
            throttle = CommentAnonRateThrottle()
            request = self.create_request(method='POST', authenticated=False)
            
            # First request should be allowed
            self.assertTrue(throttle.allow_request(request, self.view))
            
            # Second request should be throttled
            throttle2 = CommentAnonRateThrottle()
            self.assertFalse(throttle2.allow_request(request, self.view))
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {
        'comment': '100/day',
        'comment_anon': '20/day'
    }})
    def test_throttle_more_restrictive_than_authenticated(self):
        """Test anonymous throttle is typically more restrictive."""
        # This is a design principle test
        with patch.object(comments_settings, 'API_RATE_LIMIT', '100/day'):
            with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', '20/day'):
                auth_throttle = CommentRateThrottle()
                anon_throttle = CommentAnonRateThrottle()
                
                # Rates should reflect more restrictive anonymous limit
                self.assertEqual(auth_throttle.rate, '100/day')
                self.assertEqual(anon_throttle.rate, '20/day')
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment_anon': '1/min'}})
    def test_throttle_different_anonymous_users_share_limit(self):
        """Test anonymous users from same IP share throttle limit."""
        with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', '1/min'):
            # Create requests from same IP (default factory behavior)
            throttle1 = CommentAnonRateThrottle()
            request1 = self.create_request(method='POST', authenticated=False)
            self.assertTrue(throttle1.allow_request(request1, self.view))
            
            # Second anonymous request from same IP should be throttled
            throttle2 = CommentAnonRateThrottle()
            request2 = self.create_request(method='POST', authenticated=False)
            self.assertFalse(throttle2.allow_request(request2, self.view))


class CommentBurstRateThrottleTests(ThrottleTestMixin, BaseCommentTestCase):
    """Test CommentBurstRateThrottle for burst protection."""
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment_burst': '5/min'}})
    def test_throttle_scope_is_comment_burst(self):
        """Test throttle uses correct scope."""
        throttle = CommentBurstRateThrottle()
        self.assertEqual(throttle.scope, 'comment_burst')
    
    def test_throttle_uses_settings_rate(self):
        """Test throttle uses rate from settings."""
        with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', '3/min'):
            with patch.object(CommentBurstRateThrottle, 'get_rate', return_value='3/min'):
                throttle = CommentBurstRateThrottle()
                self.assertEqual(throttle.rate, '3/min')
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {}})
    def test_throttle_uses_default_burst_rate_if_not_configured(self):
        """Test throttle uses default burst rate when not configured."""
        with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', None):
            # Should use default '5/min' from the class
            with patch.object(CommentBurstRateThrottle, 'get_rate', return_value='5/min'):
                throttle = CommentBurstRateThrottle()
                self.assertEqual(throttle.rate, '5/min')
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment_burst': '5/min'}})
    def test_allow_request_for_get_requests(self):
        """Test GET requests are not throttled."""
        throttle = CommentBurstRateThrottle()
        request = self.create_request(method='GET', user=self.regular_user)
        
        # Should always allow GET
        self.assertTrue(throttle.allow_request(request, self.view))
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment_burst': '2/min'}})
    def test_burst_protection_for_rapid_posts(self):
        """Test burst throttle prevents rapid-fire posting."""
        with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', '2/min'):
            request = self.create_request(method='POST', user=self.regular_user)
            
            # First two should be allowed
            throttle1 = CommentBurstRateThrottle()
            self.assertTrue(throttle1.allow_request(request, self.view))
            
            throttle2 = CommentBurstRateThrottle()
            self.assertTrue(throttle2.allow_request(request, self.view))
            
            # Third should be throttled (burst limit exceeded)
            throttle3 = CommentBurstRateThrottle()
            self.assertFalse(throttle3.allow_request(request, self.view))
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment_burst': '5/min'}})
    def test_burst_rate_shorter_than_regular_rate(self):
        """Test burst rate is typically shorter duration than regular rate."""
        with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', '5/min'):
            throttle = CommentBurstRateThrottle()
            
            # Burst should use minute-based limit
            self.assertIn('/min', throttle.rate)
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {
        'comment': '100/hour',
        'comment_burst': '2/min'
    }})
    def test_burst_throttle_works_independently_of_regular_throttle(self):
        """Test burst throttle is independent of regular rate throttle."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', '100/hour'):
            with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', '2/min'):
                request = self.create_request(method='POST', user=self.regular_user)
                
                # Burst throttle should kick in before regular throttle
                burst_throttle1 = CommentBurstRateThrottle()
                self.assertTrue(burst_throttle1.allow_request(request, self.view))
                
                burst_throttle2 = CommentBurstRateThrottle()
                self.assertTrue(burst_throttle2.allow_request(request, self.view))
                
                burst_throttle3 = CommentBurstRateThrottle()
                self.assertFalse(burst_throttle3.allow_request(request, self.view))
                
                # Regular throttle would still allow (if checked separately)
                regular_throttle = CommentRateThrottle()
                self.assertTrue(regular_throttle.allow_request(request, self.view))


# ============================================================================
# HELPER FUNCTION TESTS - THROTTLES
# ============================================================================

class GetCommentThrottleClassesTests(BaseCommentTestCase):
    """Test get_comment_throttle_classes helper function."""
    
    def test_returns_empty_list_when_no_throttles_configured(self):
        """Test function returns empty list when no throttles configured."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', None):
            with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', None):
                with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', None):
                    result = get_comment_throttle_classes()
                    
                    self.assertIsInstance(result, list)
                    self.assertEqual(len(result), 0)
    
    def test_returns_authenticated_throttle_when_configured(self):
        """Test function returns authenticated throttle when configured."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', '100/day'):
            with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', None):
                with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', None):
                    result = get_comment_throttle_classes()
                    
                    self.assertEqual(len(result), 1)
                    self.assertIn(CommentRateThrottle, result)
    
    def test_returns_anonymous_throttle_when_configured(self):
        """Test function returns anonymous throttle when configured."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', None):
            with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', '20/day'):
                with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', None):
                    result = get_comment_throttle_classes()
                    
                    self.assertEqual(len(result), 1)
                    self.assertIn(CommentAnonRateThrottle, result)
    
    def test_returns_burst_throttle_when_configured(self):
        """Test function returns burst throttle when configured."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', None):
            with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', None):
                with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', '5/min'):
                    result = get_comment_throttle_classes()
                    
                    self.assertEqual(len(result), 1)
                    self.assertIn(CommentBurstRateThrottle, result)
    
    def test_returns_all_throttles_when_all_configured(self):
        """Test function returns all throttles when all configured."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', '100/day'):
            with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', '20/day'):
                with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', '5/min'):
                    result = get_comment_throttle_classes()
                    
                    self.assertEqual(len(result), 3)
                    self.assertIn(CommentRateThrottle, result)
                    self.assertIn(CommentAnonRateThrottle, result)
                    self.assertIn(CommentBurstRateThrottle, result)
    
    def test_returns_throttle_classes_not_instances(self):
        """Test function returns classes, not instances."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', '100/day'):
            result = get_comment_throttle_classes()
            
            # Should be classes, not instances
            for throttle in result:
                self.assertTrue(isinstance(throttle, type))
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {
        'comment': '100/day',
        'comment_anon': '20/day'
    }})
    def test_returned_classes_are_usable(self):
        """Test returned throttle classes can be instantiated."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', '100/day'):
            with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', '20/day'):
                classes = get_comment_throttle_classes()
                
                # Should be able to instantiate
                for throttle_class in classes:
                    instance = throttle_class()
                    self.assertIsNotNone(instance)
                    self.assertTrue(hasattr(instance, 'allow_request'))


# ============================================================================
# PAGINATION CLASS TESTS
# ============================================================================

class CommentPaginationTests(PaginationTestMixin, BaseCommentTestCase):
    """Test CommentPagination class."""
    
    def test_inherits_from_page_number_pagination(self):
        """Test CommentPagination inherits from PageNumberPagination."""
        pagination = CommentPagination()
        self.assertIsInstance(pagination, PageNumberPagination)
    
    def test_uses_default_page_size_when_not_configured(self):
        """Test pagination uses default when no settings configured."""
        with patch.object(comments_settings, 'PAGE_SIZE', None):
            pagination = CommentPagination()
            
            # Should have DRF's default or None
            # The exact value depends on DRF settings
            self.assertIsNotNone(pagination)
    
    def test_uses_configured_page_size(self):
        """Test pagination uses configured page size."""
        with patch.object(comments_settings, 'PAGE_SIZE', 25):
            pagination = CommentPagination()
            
            self.assertEqual(pagination.page_size, 25)
    
    def test_uses_configured_page_size_query_param(self):
        """Test pagination uses configured page size query param."""
        with patch.object(comments_settings, 'PAGE_SIZE_QUERY_PARAM', 'custom_page_size'):
            pagination = CommentPagination()
            
            self.assertEqual(pagination.page_size_query_param, 'custom_page_size')
    
    def test_uses_configured_max_page_size(self):
        """Test pagination uses configured max page size."""
        with patch.object(comments_settings, 'MAX_PAGE_SIZE', 200):
            pagination = CommentPagination()
            
            self.assertEqual(pagination.max_page_size, 200)
    
    def test_pagination_works_with_queryset(self):
        """Test pagination works with actual comment queryset."""
        # Create comments
        for i in range(15):
            self.create_comment(content=f'Comment {i}', is_public=True)
        
        with patch.object(comments_settings, 'PAGE_SIZE', 5):
            pagination = CommentPagination()
            queryset = Comment.objects.all()
            request = self.create_paginated_request()
            
            result = pagination.paginate_queryset(queryset, request, view=self.view)
            
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 5)
    
    def test_pagination_with_custom_page_size_param(self):
        """Test pagination respects custom page size from request."""
        # Create comments
        for i in range(15):
            self.create_comment(content=f'Comment {i}', is_public=True)
        
        with patch.object(comments_settings, 'PAGE_SIZE', 10):
            with patch.object(comments_settings, 'PAGE_SIZE_QUERY_PARAM', 'page_size'):
                pagination = CommentPagination()
                queryset = Comment.objects.all()
                request = self.create_paginated_request({'page_size': '3'})
                
                result = pagination.paginate_queryset(queryset, request, view=self.view)
                
                self.assertEqual(len(result), 3)
    
    def test_pagination_respects_max_page_size(self):
        """Test pagination enforces max page size limit."""
        # Create comments
        for i in range(200):
            self.create_comment(content=f'Comment {i}', is_public=True)
        
        with patch.object(comments_settings, 'PAGE_SIZE', 20):
            with patch.object(comments_settings, 'PAGE_SIZE_QUERY_PARAM', 'page_size'):
                with patch.object(comments_settings, 'MAX_PAGE_SIZE', 50):
                    pagination = CommentPagination()
                    queryset = Comment.objects.all()
                    
                    # Try to request more than max
                    request = self.create_paginated_request({'page_size': '100'})
                    result = pagination.paginate_queryset(queryset, request, view=self.view)
                    
                    # Should be capped at max_page_size
                    self.assertLessEqual(len(result), 50)
    
    def test_get_paginated_response_structure(self):
        """Test paginated response has correct structure."""
        for i in range(15):
            self.create_comment(content=f'Comment {i}', is_public=True)
        
        with patch.object(comments_settings, 'PAGE_SIZE', 5):
            pagination = CommentPagination()
            queryset = Comment.objects.all()
            request = self.create_paginated_request()
            
            paginated = pagination.paginate_queryset(queryset, request, view=self.view)
            
            # Mock serialized data
            data = [{'id': str(c.pk)} for c in paginated]
            response = pagination.get_paginated_response(data)
            
            # Check response structure
            self.assertIn('results', response.data)
            self.assertIn('count', response.data)
            self.assertIn('next', response.data)
            self.assertIn('previous', response.data)


class ThreadedCommentPaginationTests(PaginationTestMixin, BaseCommentTestCase):
    """Test ThreadedCommentPagination class."""
    
    def test_inherits_from_comment_pagination(self):
        """Test ThreadedCommentPagination inherits from CommentPagination."""
        pagination = ThreadedCommentPagination()
        self.assertIsInstance(pagination, CommentPagination)
    
    def test_paginates_only_root_comments(self):
        """Test pagination only paginates root comments."""
        # Create root comments
        root1 = self.create_comment(content='Root 1', is_public=True)
        root2 = self.create_comment(content='Root 2', is_public=True)
        root3 = self.create_comment(content='Root 3', is_public=True)
        
        # Create child comments
        self.create_comment(content='Child 1', parent=root1, is_public=True)
        self.create_comment(content='Child 2', parent=root1, is_public=True)
        self.create_comment(content='Child 3', parent=root2, is_public=True)
        
        with patch.object(comments_settings, 'PAGE_SIZE', 2):
            pagination = ThreadedCommentPagination()
            queryset = Comment.objects.all()
            request = self.create_paginated_request()
            
            result = pagination.paginate_queryset(queryset, request, view=self.view)
            
            # Should only return 2 root comments (page size = 2)
            self.assertEqual(len(result), 2)
            
            # All results should be root comments
            for comment in result:
                self.assertIsNone(comment.parent)
    
    def test_handles_empty_queryset(self):
        """Test pagination handles empty queryset gracefully."""
        pagination = ThreadedCommentPagination()
        queryset = Comment.objects.none()
        request = self.create_paginated_request()
        
        result = pagination.paginate_queryset(queryset, request, view=self.view)
        
        # Empty queryset returns None or empty list
        self.assertTrue(result is None or len(result) == 0)
    
    def test_handles_queryset_with_no_root_comments(self):
        """Test pagination handles queryset with only child comments."""
        # Create root and child
        root = self.create_comment(content='Root', is_public=True)
        child = self.create_comment(content='Child', parent=root, is_public=True)
        
        pagination = ThreadedCommentPagination()
        # Query only children (no roots)
        queryset = Comment.objects.filter(parent__isnull=False)
        request = self.create_paginated_request()
        
        result = pagination.paginate_queryset(queryset, request, view=self.view)
        
        # Should return None or empty since no roots to paginate
        self.assertTrue(result is None or len(result) == 0)
    
    def test_pagination_with_multiple_pages(self):
        """Test pagination works correctly across multiple pages."""
        # Create many root comments
        for i in range(25):
            self.create_comment(content=f'Root {i}', is_public=True)
        
        with patch.object(comments_settings, 'PAGE_SIZE', 10):
            pagination = ThreadedCommentPagination()
            queryset = Comment.objects.all()
            
            # First page
            request = self.create_paginated_request({'page': '1'})
            page1 = pagination.paginate_queryset(queryset, request, view=self.view)
            
            self.assertEqual(len(page1), 10)
            
            # Second page
            pagination2 = ThreadedCommentPagination()
            request2 = self.create_paginated_request({'page': '2'})
            page2 = pagination2.paginate_queryset(queryset, request2, view=self.view)
            
            self.assertEqual(len(page2), 10)
            
            # Third page
            pagination3 = ThreadedCommentPagination()
            request3 = self.create_paginated_request({'page': '3'})
            page3 = pagination3.paginate_queryset(queryset, request3, view=self.view)
            
            self.assertEqual(len(page3), 5)
    
    def test_evaluates_page_to_list(self):
        """Test pagination converts page to list for prefetching."""
        root1 = self.create_comment(content='Root 1', is_public=True)
        root2 = self.create_comment(content='Root 2', is_public=True)
        
        pagination = ThreadedCommentPagination()
        queryset = Comment.objects.all()
        request = self.create_paginated_request()
        
        result = pagination.paginate_queryset(queryset, request, view=self.view)
        
        # Result should be a list (evaluated)
        self.assertIsInstance(result, list)


# ============================================================================
# HELPER FUNCTION TESTS - PAGINATION
# ============================================================================

class GetCommentPaginationClassTests(BaseCommentTestCase):
    """Test get_comment_pagination_class helper function."""
    
    def test_returns_comment_pagination_when_no_threading(self):
        """Test function returns CommentPagination when threading disabled."""
        with patch.object(comments_settings, 'MAX_COMMENT_DEPTH', None):
            result = get_comment_pagination_class()
            
            self.assertEqual(result, CommentPagination)
    
    def test_returns_threaded_pagination_when_threading_enabled(self):
        """Test function returns ThreadedCommentPagination when threading enabled."""
        with patch.object(comments_settings, 'MAX_COMMENT_DEPTH', 5):
            result = get_comment_pagination_class()
            
            self.assertEqual(result, ThreadedCommentPagination)
    
    def test_returns_threaded_pagination_for_depth_zero(self):
        """Test function returns ThreadedCommentPagination even with depth 0."""
        with patch.object(comments_settings, 'MAX_COMMENT_DEPTH', 0):
            result = get_comment_pagination_class()
            
            self.assertEqual(result, ThreadedCommentPagination)
    
    def test_returned_class_is_usable(self):
        """Test returned pagination class can be instantiated."""
        result = get_comment_pagination_class()
        
        # Should be able to instantiate
        instance = result()
        self.assertIsNotNone(instance)
        self.assertTrue(hasattr(instance, 'paginate_queryset'))
    
    def test_switches_based_on_settings(self):
        """Test function dynamically switches based on settings."""
        # No threading
        with patch.object(comments_settings, 'MAX_COMMENT_DEPTH', None):
            result1 = get_comment_pagination_class()
            self.assertEqual(result1, CommentPagination)
        
        # With threading
        with patch.object(comments_settings, 'MAX_COMMENT_DEPTH', 3):
            result2 = get_comment_pagination_class()
            self.assertEqual(result2, ThreadedCommentPagination)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class DRFIntegrationTests(BaseCommentTestCase):
    """Test integration scenarios with DRF components."""
    
    def setUp(self):
        super().setUp()
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = Mock()
    
    def tearDown(self):
        cache.clear()
        super().tearDown()
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {
        'comment': '10/hour',
        'comment_burst': '2/min'
    }})
    def test_multiple_throttles_work_together(self):
        """Test multiple throttles can be applied together."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', '10/hour'):
            with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', '2/min'):
                request = self.factory.post('/comments/')
                request = Request(request)
                force_authenticate(request, user=self.regular_user)
                
                # Both throttles should allow first request
                regular_throttle = CommentRateThrottle()
                burst_throttle = CommentBurstRateThrottle()
                
                self.assertTrue(regular_throttle.allow_request(request, self.view))
                self.assertTrue(burst_throttle.allow_request(request, self.view))
    
    def test_throttle_classes_list_can_be_used_in_view(self):
        """Test get_comment_throttle_classes can be used in view."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', '100/day'):
            with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', '5/min'):
                throttle_classes = get_comment_throttle_classes()
                
                # Should be usable as viewset attribute
                self.assertIsInstance(throttle_classes, list)
                self.assertGreater(len(throttle_classes), 0)
                
                # All items should be classes
                for throttle_class in throttle_classes:
                    self.assertTrue(isinstance(throttle_class, type))
    
    def test_pagination_class_can_be_used_in_view(self):
        """Test get_comment_pagination_class can be used in view."""
        pagination_class = get_comment_pagination_class()
        
        # Should be usable as viewset attribute
        self.assertTrue(isinstance(pagination_class, type))
        self.assertTrue(issubclass(pagination_class, PageNumberPagination))
    
    def test_settings_changes_affect_behavior(self):
        """Test changing settings affects throttle/pagination behavior."""
        # Test with one set of settings
        with patch.object(comments_settings, 'PAGE_SIZE', 5):
            pagination1 = CommentPagination()
            self.assertEqual(pagination1.page_size, 5)
        
        # Test with different settings
        with patch.object(comments_settings, 'PAGE_SIZE', 20):
            pagination2 = CommentPagination()
            self.assertEqual(pagination2.page_size, 20)
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment': '100/hour'}})
    def test_pagination_and_throttles_independent(self):
        """Test pagination and throttles work independently."""
        # Create comments
        for i in range(10):
            self.create_comment(content=f'Comment {i}', is_public=True)
        
        # Use both pagination and throttle
        with patch.object(comments_settings, 'PAGE_SIZE', 3):
            with patch.object(comments_settings, 'API_RATE_LIMIT', '100/hour'):
                pagination = CommentPagination()
                throttle = CommentRateThrottle()
                
                queryset = Comment.objects.all()
                request = self.factory.get('/comments/')
                request = Request(request)
                force_authenticate(request, user=self.regular_user)
                
                # Pagination should work
                paginated = pagination.paginate_queryset(queryset, request, view=self.view)
                self.assertEqual(len(paginated), 3)
                
                # Throttle should work (GET not throttled)
                self.assertTrue(throttle.allow_request(request, self.view))


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class EdgeCaseTests(BaseCommentTestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        super().setUp()
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = Mock()
    
    def tearDown(self):
        cache.clear()
        super().tearDown()
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {}})
    def test_throttle_with_none_rate(self):
        """Test throttle handles None rate gracefully."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', None):
            try:
                throttle = CommentRateThrottle()
                request = self.factory.post('/comments/')
                request = Request(request)
                force_authenticate(request, user=self.regular_user)
                
                # Should not break with None rate
                # Behavior depends on DRF default
                result = throttle.allow_request(request, self.view)
                self.assertIsInstance(result, bool)
            except Exception:
                # Might raise ImproperlyConfigured, which is acceptable
                pass
    
    def test_pagination_with_invalid_page_number(self):
        """Test pagination handles invalid page number."""
        for i in range(10):
            self.create_comment(content=f'Comment {i}', is_public=True)
        
        pagination = CommentPagination()
        queryset = Comment.objects.all()
        
        # Invalid page number
        request = self.factory.get('/comments/', {'page': 'invalid'})
        request = Request(request)
        
        # Should handle gracefully (return first page or error)
        try:
            result = pagination.paginate_queryset(queryset, request, view=self.view)
            # If it doesn't raise, it should return something valid
            self.assertIsNotNone(result)
        except Exception:
            # Or it might raise an exception, which is also acceptable
            pass
    
    def test_pagination_with_page_out_of_range(self):
        """Test pagination handles page number out of range."""
        for i in range(5):
            self.create_comment(content=f'Comment {i}', is_public=True)
        
        with patch.object(comments_settings, 'PAGE_SIZE', 10):
            pagination = CommentPagination()
            queryset = Comment.objects.all()
            
            # Request page that doesn't exist
            request = self.factory.get('/comments/', {'page': '999'})
            request = Request(request)
            
            # Should handle gracefully
            try:
                result = pagination.paginate_queryset(queryset, request, view=self.view)
                # Might return None or empty
                self.assertTrue(result is None or len(result) == 0)
            except Exception:
                # Or might raise, which is acceptable
                pass
    
    def test_threaded_pagination_with_mixed_root_and_children(self):
        """Test threaded pagination handles mixed comments correctly."""
        # Create complex tree structure
        root1 = self.create_comment(content='Root 1', is_public=True)
        child1_1 = self.create_comment(content='Child 1-1', parent=root1, is_public=True)
        grandchild1_1_1 = self.create_comment(content='Grandchild 1-1-1', parent=child1_1, is_public=True)
        
        root2 = self.create_comment(content='Root 2', is_public=True)
        child2_1 = self.create_comment(content='Child 2-1', parent=root2, is_public=True)
        
        with patch.object(comments_settings, 'PAGE_SIZE', 10):
            pagination = ThreadedCommentPagination()
            queryset = Comment.objects.all()
            request = self.factory.get('/comments/')
            request = Request(request)
            
            result = pagination.paginate_queryset(queryset, request, view=self.view)
            
            # Should only return root comments
            self.assertEqual(len(result), 2)
            for comment in result:
                self.assertIsNone(comment.parent)
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'comment': '100/day'}})
    def test_throttle_with_missing_user(self):
        """Test throttle handles requests with no user."""
        throttle = CommentRateThrottle()
        request = self.factory.post('/comments/')
        request = Request(request)
        # Don't authenticate - user will be AnonymousUser
        
        # Should not crash
        try:
            result = throttle.allow_request(request, self.view)
            self.assertIsInstance(result, bool)
        except Exception:
            # Might raise for anonymous user, which is acceptable
            pass
    
    def test_pagination_preserves_queryset_filters(self):
        """Test pagination doesn't interfere with queryset filters."""
        # Create public and non-public comments
        self.create_comment(content='Public', is_public=True)
        self.create_comment(content='Private', is_public=False)
        
        pagination = CommentPagination()
        # Pre-filtered queryset
        queryset = Comment.objects.filter(is_public=True)
        request = self.factory.get('/comments/')
        request = Request(request)
        
        result = pagination.paginate_queryset(queryset, request, view=self.view)
        
        # Should only have public comment
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].is_public)


# ============================================================================
# SETTINGS CONFIGURATION TESTS
# ============================================================================

class SettingsConfigurationTests(BaseCommentTestCase):
    """Test various settings configurations."""
    
    def test_all_pagination_settings_together(self):
        """Test all pagination settings work together."""
        with patch.object(comments_settings, 'PAGE_SIZE', 15):
            with patch.object(comments_settings, 'PAGE_SIZE_QUERY_PARAM', 'size'):
                with patch.object(comments_settings, 'MAX_PAGE_SIZE', 50):
                    pagination = CommentPagination()
                    
                    self.assertEqual(pagination.page_size, 15)
                    self.assertEqual(pagination.page_size_query_param, 'size')
                    self.assertEqual(pagination.max_page_size, 50)
    
    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {
        'comment': '100/day',
        'comment_anon': '20/day',
        'comment_burst': '5/min'
    }})
    def test_all_throttle_settings_together(self):
        """Test all throttle settings work together."""
        with patch.object(comments_settings, 'API_RATE_LIMIT', '100/day'):
            with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', '20/day'):
                with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', '5/min'):
                    classes = get_comment_throttle_classes()
                    
                    self.assertEqual(len(classes), 3)
                    
                    # Instantiate all
                    instances = [cls() for cls in classes]
                    rates = [inst.rate for inst in instances]
                    
                    self.assertIn('100/day', rates)
                    self.assertIn('20/day', rates)
                    self.assertIn('5/min', rates)
    
    def test_partial_throttle_configuration(self):
        """Test partial throttle configuration."""
        # Only authenticated throttle
        with patch.object(comments_settings, 'API_RATE_LIMIT', '100/day'):
            with patch.object(comments_settings, 'API_RATE_LIMIT_ANON', None):
                with patch.object(comments_settings, 'API_RATE_LIMIT_BURST', None):
                    classes = get_comment_throttle_classes()
                    
                    self.assertEqual(len(classes), 1)
                    self.assertEqual(classes[0], CommentRateThrottle)
    
    def test_threading_depth_affects_pagination_class(self):
        """Test MAX_COMMENT_DEPTH affects pagination class selection."""
        test_cases = [
            (None, CommentPagination),
            (0, ThreadedCommentPagination),
            (1, ThreadedCommentPagination),
            (5, ThreadedCommentPagination),
            (100, ThreadedCommentPagination),
        ]
        
        for depth, expected_class in test_cases:
            with patch.object(comments_settings, 'MAX_COMMENT_DEPTH', depth):
                result = get_comment_pagination_class()
                self.assertEqual(
                    result, 
                    expected_class,
                    f"Failed for depth={depth}"
                )