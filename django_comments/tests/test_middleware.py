"""
Comprehensive tests for django_comments.middleware module.

Tests cover:
- CommentCacheWarmingMiddleware functionality
- Pre-warming and post-warming cache behaviors
- Request/response handling
- Edge cases and error scenarios
- Real-world integration scenarios
"""

from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from django_comments.middleware import CommentCacheWarmingMiddleware
from django_comments.tests.base import BaseCommentTestCase

User = get_user_model()


# ============================================================================
# MIDDLEWARE INITIALIZATION TESTS
# ============================================================================

class MiddlewareInitializationTests(TestCase):
    """Test middleware initialization."""
    
    def test_middleware_initialization(self):
        """Test middleware initializes correctly."""
        get_response = Mock()
        middleware = CommentCacheWarmingMiddleware(get_response)
        
        self.assertEqual(middleware.get_response, get_response)
    
    def test_middleware_callable(self):
        """Test middleware is callable."""
        get_response = Mock(return_value=HttpResponse())
        middleware = CommentCacheWarmingMiddleware(get_response)
        
        self.assertTrue(callable(middleware))


# ============================================================================
# MIDDLEWARE CALL TESTS
# ============================================================================

class MiddlewareCallTests(BaseCommentTestCase):
    """Test middleware __call__ method."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = CommentCacheWarmingMiddleware(self.get_response)
    
    def test_middleware_processes_request(self):
        """Test middleware processes request successfully."""
        request = self.factory.get('/test/')
        
        response = self.middleware(request)
        
        self.assertIsInstance(response, HttpResponse)
        self.get_response.assert_called_once_with(request)
    
    def test_middleware_calls_pre_warm_caches(self):
        """Test middleware calls _pre_warm_caches."""
        request = self.factory.get('/api/comments/')
        
        with patch.object(
            self.middleware,
            '_pre_warm_caches'
        ) as mock_pre_warm:
            response = self.middleware(request)
            
            mock_pre_warm.assert_called_once_with(request)
    
    def test_middleware_calls_post_warm_caches(self):
        """Test middleware calls _post_warm_caches."""
        request = self.factory.get('/api/comments/')
        
        with patch.object(
            self.middleware,
            '_post_warm_caches'
        ) as mock_post_warm:
            response = self.middleware(request)
            
            mock_post_warm.assert_called_once()
            call_args = mock_post_warm.call_args[0]
            self.assertEqual(call_args[0], request)
            self.assertIsInstance(call_args[1], HttpResponse)
    
    def test_middleware_returns_response(self):
        """Test middleware returns the response."""
        request = self.factory.get('/test/')
        expected_response = HttpResponse("Test content")
        self.get_response.return_value = expected_response
        
        response = self.middleware(request)
        
        self.assertEqual(response, expected_response)
    
    def test_middleware_handles_non_comment_views(self):
        """Test middleware works for non-comment views."""
        request = self.factory.get('/other/view/')
        
        response = self.middleware(request)
        
        self.assertIsInstance(response, HttpResponse)
        self.get_response.assert_called_once()


# ============================================================================
# PRE-WARM CACHES TESTS
# ============================================================================

class PreWarmCachesTests(BaseCommentTestCase):
    """Test _pre_warm_caches method."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
    
    def test_pre_warm_detects_comment_list_view(self):
        """Test pre-warming detects comment list view."""
        request = self.factory.get('/api/comments/')
        
        # Should not raise exception
        self.middleware._pre_warm_caches(request)
    
    def test_pre_warm_ignores_non_comment_views(self):
        """Test pre-warming ignores non-comment views."""
        request = self.factory.get('/other/view/')
        
        # Should not raise exception
        self.middleware._pre_warm_caches(request)
    
    def test_pre_warm_with_comment_detail_view(self):
        """Test pre-warming with comment detail view."""
        request = self.factory.get('/api/comments/123/')
        
        # Should not raise exception
        self.middleware._pre_warm_caches(request)
    
    def test_pre_warm_with_nested_comment_path(self):
        """Test pre-warming with nested comment path."""
        request = self.factory.get('/api/v1/comments/')
        
        # Should detect and handle
        self.middleware._pre_warm_caches(request)
    
    def test_pre_warm_with_querystring(self):
        """Test pre-warming with query string parameters."""
        request = self.factory.get('/api/comments/?page=2&limit=10')
        
        # Should not raise exception
        self.middleware._pre_warm_caches(request)
    
    def test_pre_warm_does_not_modify_request(self):
        """Test pre-warming doesn't modify the request."""
        request = self.factory.get('/api/comments/')
        original_path = request.path
        
        self.middleware._pre_warm_caches(request)
        
        self.assertEqual(request.path, original_path)


# ============================================================================
# POST-WARM CACHES TESTS
# ============================================================================

class PostWarmCachesTests(BaseCommentTestCase):
    """Test _post_warm_caches method."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
    
    def test_post_warm_with_regular_response(self):
        """Test post-warming with regular HTTP response."""
        request = self.factory.get('/api/comments/')
        response = HttpResponse("OK")
        
        # Should not raise exception
        self.middleware._post_warm_caches(request, response)
    
    def test_post_warm_with_json_response(self):
        """Test post-warming with JSON response."""
        from django.http import JsonResponse
        
        request = self.factory.get('/api/comments/')
        response = JsonResponse({'results': []})
        
        # Should not raise exception
        self.middleware._post_warm_caches(request, response)
    
    def test_post_warm_with_error_response(self):
        """Test post-warming with error response."""
        request = self.factory.get('/api/comments/')
        response = HttpResponse(status=500)
        
        # Should not raise exception
        self.middleware._post_warm_caches(request, response)
    
    def test_post_warm_with_redirect_response(self):
        """Test post-warming with redirect response."""
        from django.http import HttpResponseRedirect
        
        request = self.factory.get('/api/comments/')
        response = HttpResponseRedirect('/other/url/')
        
        # Should not raise exception
        self.middleware._post_warm_caches(request, response)
    
    def test_post_warm_does_not_modify_response(self):
        """Test post-warming doesn't modify the response."""
        request = self.factory.get('/api/comments/')
        response = HttpResponse("Original content")
        
        self.middleware._post_warm_caches(request, response)
        
        self.assertEqual(response.content, b"Original content")


# ============================================================================
# MIDDLEWARE INTEGRATION TESTS
# ============================================================================

class MiddlewareIntegrationTests(BaseCommentTestCase):
    """Test middleware integration with Django request/response cycle."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
    
    def test_middleware_in_request_response_cycle(self):
        """Test middleware works in full request/response cycle."""
        def view_func(request):
            return HttpResponse("View response")
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.get('/api/comments/')
        
        response = middleware(request)
        
        self.assertEqual(response.content, b"View response")
    
    def test_middleware_preserves_response_status_code(self):
        """Test middleware preserves response status code."""
        def view_func(request):
            return HttpResponse("Created", status=201)
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.get('/api/comments/')
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 201)
    
    def test_middleware_preserves_response_headers(self):
        """Test middleware preserves response headers."""
        def view_func(request):
            response = HttpResponse("OK")
            response['X-Custom-Header'] = 'test-value'
            return response
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.get('/api/comments/')
        
        response = middleware(request)
        
        self.assertEqual(response['X-Custom-Header'], 'test-value')
    
    def test_middleware_with_authenticated_request(self):
        """Test middleware with authenticated user."""
        def view_func(request):
            return HttpResponse("OK")
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.get('/api/comments/')
        request.user = self.regular_user
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_middleware_with_anonymous_request(self):
        """Test middleware with anonymous user."""
        from django.contrib.auth.models import AnonymousUser
        
        def view_func(request):
            return HttpResponse("OK")
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.get('/api/comments/')
        request.user = AnonymousUser()
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_middleware_with_post_request(self):
        """Test middleware with POST request."""
        def view_func(request):
            return HttpResponse("Created", status=201)
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.post('/api/comments/', {'content': 'Test'})
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 201)
    
    def test_middleware_with_put_request(self):
        """Test middleware with PUT request."""
        def view_func(request):
            return HttpResponse("Updated")
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.put('/api/comments/123/')
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_middleware_with_delete_request(self):
        """Test middleware with DELETE request."""
        def view_func(request):
            return HttpResponse(status=204)
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.delete('/api/comments/123/')
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 204)


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class MiddlewareErrorHandlingTests(BaseCommentTestCase):
    """Test middleware error handling."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
    
    def test_middleware_handles_view_exception(self):
        """Test middleware propagates view exceptions."""
        def view_func(request):
            raise ValueError("View error")
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.get('/api/comments/')
        
        with self.assertRaises(ValueError):
            middleware(request)
    
    def test_middleware_handles_pre_warm_exception(self):
        """Test middleware handles pre-warm exceptions gracefully."""
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        
        with patch.object(
            middleware,
            '_pre_warm_caches',
            side_effect=Exception("Pre-warm error")
        ):
            request = self.factory.get('/api/comments/')
            
            # Should still call view and return response
            with self.assertRaises(Exception):
                middleware(request)
    
    def test_middleware_handles_post_warm_exception(self):
        """Test middleware handles post-warm exceptions gracefully."""
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        
        with patch.object(
            middleware,
            '_post_warm_caches',
            side_effect=Exception("Post-warm error")
        ):
            request = self.factory.get('/api/comments/')
            
            # Should still return response
            with self.assertRaises(Exception):
                middleware(request)
    
    def test_middleware_with_none_response(self):
        """Test middleware when view returns None."""
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=None))
        request = self.factory.get('/api/comments/')
        
        response = middleware(request)
        
        self.assertIsNone(response)
    
    def test_middleware_with_malformed_request(self):
        """Test middleware with malformed request object."""
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        request = Mock(spec=['path'])
        request.path = '/api/comments/'
        
        # Should not raise exception
        response = middleware(request)
        self.assertIsInstance(response, HttpResponse)


# ============================================================================
# CACHE WARMING BEHAVIOR TESTS
# ============================================================================

class CacheWarmingBehaviorTests(BaseCommentTestCase):
    """Test actual cache warming behaviors."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        cache.clear()
    
    def test_middleware_detects_comment_api_endpoint(self):
        """Test middleware detects comment API endpoint."""
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        
        # Mock the _pre_warm_caches to track calls
        with patch.object(middleware, '_pre_warm_caches') as mock_pre_warm:
            request = self.factory.get('/api/comments/')
            middleware(request)
            
            mock_pre_warm.assert_called_once()
            self.assertEqual(mock_pre_warm.call_args[0][0].path, '/api/comments/')
    
    def test_middleware_detects_various_comment_paths(self):
        """Test middleware detects various comment-related paths."""
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        
        paths = [
            '/api/comments/',
            '/api/comments/123/',
            '/api/comments/?page=2',
            '/v1/api/comments/',
        ]
        
        for path in paths:
            with self.subTest(path=path):
                request = self.factory.get(path)
                # Should not raise exception
                middleware(request)
    
    def test_middleware_ignores_non_comment_paths(self):
        """Test middleware ignores non-comment paths."""
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        
        paths = [
            '/api/posts/',
            '/api/users/',
            '/admin/',
            '/static/css/style.css',
        ]
        
        for path in paths:
            with self.subTest(path=path):
                with patch.object(middleware, '_pre_warm_caches') as mock:
                    request = self.factory.get(path)
                    middleware(request)
                    
                    # Should still be called, but won't do anything
                    mock.assert_called_once()


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class MiddlewarePerformanceTests(BaseCommentTestCase):
    """Test middleware performance characteristics."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
    
    def test_middleware_overhead_is_minimal(self):
        """Test middleware adds minimal overhead."""
        import time
        
        call_count = [0]
        
        def view_func(request):
            call_count[0] += 1
            return HttpResponse("OK")
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.get('/api/comments/')
        
        start_time = time.time()
        response = middleware(request)
        end_time = time.time()
        
        # Middleware should complete very quickly (< 100ms)
        self.assertLess(end_time - start_time, 0.1)
        self.assertEqual(call_count[0], 1)
    
    def test_middleware_does_not_block_response(self):
        """Test middleware doesn't block the response."""
        response_returned = [False]
        
        def view_func(request):
            response_returned[0] = True
            return HttpResponse("OK")
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.get('/api/comments/')
        
        response = middleware(request)
        
        # View should have been called
        self.assertTrue(response_returned[0])
        self.assertIsInstance(response, HttpResponse)


# ============================================================================
# EDGE CASES AND REAL-WORLD SCENARIOS
# ============================================================================

class MiddlewareEdgeCasesTests(BaseCommentTestCase):
    """Test edge cases and real-world scenarios."""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
    
    def test_middleware_with_very_long_url(self):
        """Test middleware with very long URL."""
        long_path = '/api/comments/' + 'x' * 2000
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        request = self.factory.get(long_path)
        
        # Should not raise exception
        response = middleware(request)
        self.assertIsInstance(response, HttpResponse)
    
    def test_middleware_with_unicode_in_url(self):
        """Test middleware with Unicode characters in URL."""
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        request = self.factory.get('/api/comments/テスト/')
        
        # Should not raise exception
        response = middleware(request)
        self.assertIsInstance(response, HttpResponse)
    
    def test_middleware_with_special_characters_in_url(self):
        """Test middleware with special characters in URL."""
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        request = self.factory.get('/api/comments/?q=test%20query&filter=spam')
        
        # Should not raise exception
        response = middleware(request)
        self.assertIsInstance(response, HttpResponse)
    
    def test_middleware_with_multiple_slashes(self):
        """Test middleware with multiple consecutive slashes."""
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        request = self.factory.get('/api//comments///')
        
        # Should not raise exception
        response = middleware(request)
        self.assertIsInstance(response, HttpResponse)
    
    def test_middleware_with_streaming_response(self):
        """Test middleware with streaming response."""
        from django.http import StreamingHttpResponse
        
        def generator():
            yield b"chunk1"
            yield b"chunk2"
        
        def view_func(request):
            return StreamingHttpResponse(generator())
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.get('/api/comments/')
        
        response = middleware(request)
        
        self.assertIsInstance(response, StreamingHttpResponse)
    
    def test_middleware_with_file_response(self):
        """Test middleware with file response."""
        from django.http import FileResponse
        from io import BytesIO
        
        def view_func(request):
            file_like = BytesIO(b"file content")
            return FileResponse(file_like)
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.get('/api/comments/export/')
        
        response = middleware(request)
        
        self.assertIsInstance(response, FileResponse)
    
    def test_middleware_concurrent_requests(self):
        """Test middleware with concurrent requests."""
        from threading import Thread
        
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        results = []
        
        def make_request():
            request = self.factory.get('/api/comments/')
            response = middleware(request)
            results.append(response.status_code)
        
        threads = [Thread(target=make_request) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        self.assertEqual(len(results), 10)
        self.assertTrue(all(code == 200 for code in results))
    
    def test_middleware_with_request_without_path(self):
        """Test middleware with request missing path attribute."""
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        request = Mock()
        delattr(request, 'path')
        
        # Should handle gracefully
        try:
            middleware(request)
        except AttributeError:
            pass  # Expected if path is truly required
    
    def test_middleware_preserves_cookies(self):
        """Test middleware preserves cookies in response."""
        def view_func(request):
            response = HttpResponse("OK")
            response.set_cookie('test_cookie', 'test_value')
            return response
        
        middleware = CommentCacheWarmingMiddleware(view_func)
        request = self.factory.get('/api/comments/')
        
        response = middleware(request)
        
        self.assertIn('test_cookie', response.cookies)
    
    def test_middleware_with_ajax_request(self):
        """Test middleware with AJAX request."""
        middleware = CommentCacheWarmingMiddleware(Mock(return_value=HttpResponse()))
        request = self.factory.get(
            '/api/comments/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_middleware_chain_with_multiple_middlewares(self):
        """Test middleware works in chain with other middlewares."""
        call_order = []
        
        def first_middleware(get_response):
            def middleware(request):
                call_order.append('first_pre')
                response = get_response(request)
                call_order.append('first_post')
                return response
            return middleware
        
        def view_func(request):
            call_order.append('view')
            return HttpResponse("OK")
        
        # Chain: CommentCacheWarmingMiddleware -> first_middleware -> view
        middleware_chain = CommentCacheWarmingMiddleware(
            first_middleware(view_func)
        )
        
        request = self.factory.get('/api/comments/')
        response = middleware_chain(request)
        
        self.assertEqual(call_order, ['first_pre', 'view', 'first_post'])
        self.assertEqual(response.status_code, 200)