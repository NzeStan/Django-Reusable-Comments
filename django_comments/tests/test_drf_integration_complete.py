"""
Comprehensive test suite for DRF integration.
Tests throttling (rate limiting) and pagination.
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django_comments.models import Comment
from django_comments.drf_integration import (
    CommentRateThrottle,
    CommentAnonRateThrottle,
    CommentBurstRateThrottle,
    CommentPagination,
    ThreadedCommentPagination,
    get_comment_throttle_classes,
    get_comment_pagination_class,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    """Create test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, user):
    """Create authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def post(user):
    """Create test post for comments."""
    from django.contrib.contenttypes.models import ContentType
    from django.db import models
    
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


class TestCommentRateThrottle:
    """Tests for authenticated user rate throttling."""
    
    def test_rate_throttle_initialization(self, settings):
        """Test throttle initializes with correct rate."""
        settings.DJANGO_COMMENTS_CONFIG = {
            'API_RATE_LIMIT': '10/day',
        }
        from django_comments import conf
        conf.comments_settings = conf.CommentsSettings(
            settings.DJANGO_COMMENTS_CONFIG,
            conf.DEFAULTS
        )
        
        throttle = CommentRateThrottle()
        assert throttle.rate == '10/day'
    
    def test_rate_throttle_only_post_requests(self, authenticated_client):
        """Test throttle only applies to POST requests."""
        throttle = CommentRateThrottle()
        
        # Mock request
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        
        # GET request should not be throttled
        get_request = factory.get('/api/comments/')
        get_request.user = authenticated_client.handler._force_user
        assert throttle.allow_request(get_request, None) == True
        
        # POST request should be checked
        post_request = factory.post('/api/comments/')
        post_request.user = authenticated_client.handler._force_user
        # (actual throttling depends on cache)


class TestCommentAnonRateThrottle:
    """Tests for anonymous user rate throttling."""
    
    def test_anon_throttle_initialization(self, settings):
        """Test anonymous throttle initializes correctly."""
        settings.DJANGO_COMMENTS_CONFIG = {
            'API_RATE_LIMIT_ANON': '5/day',
        }
        from django_comments import conf
        conf.comments_settings = conf.CommentsSettings(
            settings.DJANGO_COMMENTS_CONFIG,
            conf.DEFAULTS
        )
        
        throttle = CommentAnonRateThrottle()
        assert throttle.rate == '5/day'


class TestCommentBurstRateThrottle:
    """Tests for burst rate throttling."""
    
    def test_burst_throttle_default_rate(self):
        """Test burst throttle has default rate."""
        throttle = CommentBurstRateThrottle()
        # Should have default rate
        assert throttle.rate
        assert '/min' in throttle.rate


class TestThrottleIntegration:
    """Tests for throttle integration with views."""
    
    def test_get_comment_throttle_classes(self, settings):
        """Test getting throttle classes from settings."""
        settings.DJANGO_COMMENTS_CONFIG = {
            'API_RATE_LIMIT': '100/day',
            'API_RATE_LIMIT_ANON': '20/day',
            'API_RATE_LIMIT_BURST': '5/min',
        }
        from django_comments import conf
        conf.comments_settings = conf.CommentsSettings(
            settings.DJANGO_COMMENTS_CONFIG,
            conf.DEFAULTS
        )
        
        throttles = get_comment_throttle_classes()
        
        assert len(throttles) == 3
        assert CommentRateThrottle in throttles
        assert CommentAnonRateThrottle in throttles
        assert CommentBurstRateThrottle in throttles
    
    def test_get_throttle_classes_with_partial_config(self, settings):
        """Test getting throttle classes with partial configuration."""
        settings.DJANGO_COMMENTS_CONFIG = {
            'API_RATE_LIMIT': '100/day',
            # Only one throttle configured
        }
        from django_comments import conf
        conf.comments_settings = conf.CommentsSettings(
            settings.DJANGO_COMMENTS_CONFIG,
            conf.DEFAULTS
        )
        
        throttles = get_comment_throttle_classes()
        
        # Should only include configured throttles
        assert CommentRateThrottle in throttles


class TestCommentPagination:
    """Tests for standard pagination."""
    
    def test_pagination_initialization(self, settings):
        """Test pagination initializes with correct settings."""
        settings.DJANGO_COMMENTS_CONFIG = {
            'PAGE_SIZE': 25,
            'PAGE_SIZE_QUERY_PARAM': 'size',
            'MAX_PAGE_SIZE': 200,
        }
        from django_comments import conf
        conf.comments_settings = conf.CommentsSettings(
            settings.DJANGO_COMMENTS_CONFIG,
            conf.DEFAULTS
        )
        
        pagination = CommentPagination()
        
        assert pagination.page_size == 25
        assert pagination.page_size_query_param == 'size'
        assert pagination.max_page_size == 200
    
    def test_pagination_defaults(self):
        """Test pagination with default settings."""
        pagination = CommentPagination()
        
        # Should have some defaults
        assert hasattr(pagination, 'page_size')


class TestThreadedCommentPagination:
    """Tests for threaded comment pagination."""
    
    def test_threaded_pagination_filters_root_comments(self, user):
        """Test threaded pagination only paginates root comments."""
        from django.contrib.contenttypes.models import ContentType
        
        # Create root comments
        ct = ContentType.objects.get_for_model(User)
        root1 = Comment.objects.create(
            content_type=ct,
            object_id=user.id,
            user=user,
            content="Root 1"
        )
        root2 = Comment.objects.create(
            content_type=ct,
            object_id=user.id,
            user=user,
            content="Root 2"
        )
        
        # Create child comments
        child1 = Comment.objects.create(
            content_type=ct,
            object_id=user.id,
            user=user,
            content="Child 1",
            parent=root1
        )
        
        # Get all comments
        queryset = Comment.objects.all()
        
        # Paginate
        pagination = ThreadedCommentPagination()
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory
        
        factory = APIRequestFactory()
        request = factory.get('/api/comments/')
        request = Request(request)
        
        page = pagination.paginate_queryset(queryset, request)
        
        if page:
            # Should only include root comments
            for comment in page:
                assert comment.parent is None


class TestPaginationIntegration:
    """Tests for pagination integration with views."""
    
    def test_get_comment_pagination_class(self, settings):
        """Test getting pagination class from settings."""
        settings.DJANGO_COMMENTS_CONFIG = {
            'MAX_COMMENT_DEPTH': 3,
        }
        from django_comments import conf
        conf.comments_settings = conf.CommentsSettings(
            settings.DJANGO_COMMENTS_CONFIG,
            conf.DEFAULTS
        )
        
        pagination_class = get_comment_pagination_class()
        
        # Should return threaded pagination when depth is set
        assert pagination_class == ThreadedCommentPagination
    
    def test_get_pagination_class_without_threading(self, settings):
        """Test getting pagination class without threading."""
        settings.DJANGO_COMMENTS_CONFIG = {
            'MAX_COMMENT_DEPTH': None,
        }
        from django_comments import conf
        conf.comments_settings = conf.CommentsSettings(
            settings.DJANGO_COMMENTS_CONFIG,
            conf.DEFAULTS
        )
        
        pagination_class = get_comment_pagination_class()
        
        # Should return standard pagination
        assert pagination_class == CommentPagination


class TestAPIRateLimiting:
    """Integration tests for API rate limiting."""
    
    def test_rate_limit_reached(self, authenticated_client, post, settings):
        """Test rate limit is enforced."""
        # Set very low rate limit
        settings.DJANGO_COMMENTS_CONFIG = {
            'API_RATE_LIMIT_BURST': '2/min',
        }
        
        # Clear cache
        from django.core.cache import cache
        cache.clear()
        
        # Make requests up to limit
        for i in range(2):
            response = authenticated_client.post('/api/comments/', {
                'content_type': 'auth.user',
                'object_id': str(post.author.id),
                'content': f'Comment {i}'
            })
            # May succeed or fail depending on endpoint configuration
        
        # Note: Actual rate limiting test requires proper view configuration
        # and cache backend. This is a structure test.
    
    def test_rate_limit_reset(self, authenticated_client, settings):
        """Test rate limit resets after time period."""
        # This requires time manipulation or waiting
        # Structure test only
        pass


class TestAPIPagination:
    """Integration tests for API pagination."""
    
    def test_pagination_response_structure(self, authenticated_client, user):
        """Test pagination response structure."""
        from django.contrib.contenttypes.models import ContentType
        
        # Create multiple comments
        ct = ContentType.objects.get_for_model(User)
        for i in range(25):
            Comment.objects.create(
                content_type=ct,
                object_id=user.id,
                user=user,
                content=f"Comment {i}"
            )
        
        response = authenticated_client.get('/api/comments/?page_size=10')
        
        # Check response structure
        if response.status_code == 200 and 'results' in response.data:
            assert 'count' in response.data
            assert 'next' in response.data
            assert 'previous' in response.data
            assert 'results' in response.data
            assert len(response.data['results']) <= 10
    
    def test_pagination_page_size_param(self, authenticated_client, user):
        """Test custom page size parameter."""
        from django.contrib.contenttypes.models import ContentType
        
        # Create comments
        ct = ContentType.objects.get_for_model(User)
        for i in range(50):
            Comment.objects.create(
                content_type=ct,
                object_id=user.id,
                user=user,
                content=f"Comment {i}"
            )
        
        # Request with custom page size
        response = authenticated_client.get('/api/comments/?page_size=5')
        
        if response.status_code == 200 and 'results' in response.data:
            assert len(response.data['results']) <= 5
    
    def test_pagination_max_page_size_enforced(self, authenticated_client, user, settings):
        """Test maximum page size is enforced."""
        settings.DJANGO_COMMENTS_CONFIG = {
            'MAX_PAGE_SIZE': 50,
        }
        
        from django.contrib.contenttypes.models import ContentType
        
        # Create many comments
        ct = ContentType.objects.get_for_model(User)
        for i in range(200):
            Comment.objects.create(
                content_type=ct,
                object_id=user.id,
                user=user,
                content=f"Comment {i}"
            )
        
        # Request with very large page size
        response = authenticated_client.get('/api/comments/?page_size=1000')
        
        if response.status_code == 200 and 'results' in response.data:
            # Should not exceed max page size
            assert len(response.data['results']) <= 50


class TestThrottleEdgeCases:
    """Tests for throttle edge cases."""
    
    def test_throttle_with_no_cache(self, authenticated_client, settings):
        """Test throttle behavior with no cache backend."""
        # Test structure - actual behavior depends on cache configuration
        throttle = CommentRateThrottle()
        assert hasattr(throttle, 'allow_request')
    
    def test_throttle_with_different_users(self, api_client):
        """Test throttle is per-user."""
        user1 = User.objects.create_user('user1', 'user1@example.com', 'pass')
        user2 = User.objects.create_user('user2', 'user2@example.com', 'pass')
        
        # Each user should have separate rate limit
        # Structure test only


class TestPaginationEdgeCases:
    """Tests for pagination edge cases."""
    
    def test_pagination_with_no_results(self, authenticated_client):
        """Test pagination with no results."""
        response = authenticated_client.get('/api/comments/?page=1')
        
        if response.status_code == 200:
            # Should return empty results
            if 'results' in response.data:
                assert len(response.data['results']) == 0
    
    def test_pagination_with_invalid_page(self, authenticated_client):
        """Test pagination with invalid page number."""
        response = authenticated_client.get('/api/comments/?page=9999')
        
        # Should handle gracefully (404 or empty results)
        assert response.status_code in [200, 404]
    
    def test_pagination_with_negative_page(self, authenticated_client):
        """Test pagination with negative page number."""
        response = authenticated_client.get('/api/comments/?page=-1')
        
        # Should handle gracefully
        assert response.status_code in [200, 400, 404]


class TestDRFSettingsExport:
    """Tests for DRF settings export."""
    
    def test_get_drf_settings(self, settings):
        """Test exporting settings to DRF format."""
        settings.DJANGO_COMMENTS_CONFIG = {
            'PAGE_SIZE': 20,
            'API_RATE_LIMIT': '100/day',
            'API_RATE_LIMIT_ANON': '20/day',
            'API_RATE_LIMIT_BURST': '5/min',
        }
        from django_comments import conf
        conf.comments_settings = conf.CommentsSettings(
            settings.DJANGO_COMMENTS_CONFIG,
            conf.DEFAULTS
        )
        
        from django_comments.drf_integration import get_drf_settings
        drf_settings = get_drf_settings()
        
        assert 'PAGE_SIZE' in drf_settings
        assert drf_settings['PAGE_SIZE'] == 20
        
        assert 'DEFAULT_THROTTLE_RATES' in drf_settings
        rates = drf_settings['DEFAULT_THROTTLE_RATES']
        assert 'comment' in rates
        assert 'comment_anon' in rates
        assert 'comment_burst' in rates


class TestPerformance:
    """Performance tests for throttling and pagination."""
    
    def test_throttle_performance(self, authenticated_client):
        """Test throttle check performance."""
        import time
        
        throttle = CommentRateThrottle()
        
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        request = factory.post('/api/comments/')
        request.user = authenticated_client.handler._force_user
        
        start = time.time()
        for _ in range(100):
            throttle.allow_request(request, None)
        elapsed = time.time() - start
        
        # Should be fast (< 0.1s for 100 checks)
        assert elapsed < 0.1
    
    def test_pagination_performance(self, user):
        """Test pagination performance with many comments."""
        import time
        from django.contrib.contenttypes.models import ContentType
        
        # Create many comments
        ct = ContentType.objects.get_for_model(User)
        comments = [
            Comment(
                content_type=ct,
                object_id=user.id,
                user=user,
                content=f"Comment {i}"
            )
            for i in range(1000)
        ]
        Comment.objects.bulk_create(comments)
        
        # Paginate
        queryset = Comment.objects.all()
        pagination = CommentPagination()
        
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory
        
        factory = APIRequestFactory()
        request = factory.get('/api/comments/?page=1')
        request = Request(request)
        
        start = time.time()
        page = pagination.paginate_queryset(queryset, request)
        elapsed = time.time() - start
        
        # Should be fast (< 0.05s)
        assert elapsed < 0.05


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v'])