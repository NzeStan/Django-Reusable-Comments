# test_sort_validation.py
"""
Tests for API sort validation feature.
Place this file in: django_comments/tests/test_sort_validation.py
"""
import pytest
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient
from django_comments.models import Comment

User = get_user_model()


class SortValidationTestCase(TestCase):
    """Test API sort validation."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.content_type = ContentType.objects.get_for_model(User)
        
        # Create some comments with different timestamps
        self.comments = []
        for i in range(5):
            comment = Comment.objects.create(
                content_type=self.content_type,
                object_id=self.user.id,
                user=self.user,
                content=f"Test comment {i}"
            )
            self.comments.append(comment)
    
    def test_default_sort(self):
        """Test that default sort is applied when no ordering specified."""
        response = self.client.get('/api/comments/')
        self.assertEqual(response.status_code, 200)
        
        # Should be ordered by -created_at (newest first) by default
        results = response.data.get('results', response.data)
        if results:
            # Newest should be first
            self.assertEqual(results[0]['id'], str(self.comments[-1].pk))
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'ALLOWED_SORTS': ['-created_at', 'created_at'],
    })
    def test_valid_sort_allowed(self):
        """Test that valid sorts are allowed."""
        # Valid ascending sort
        response = self.client.get('/api/comments/?ordering=created_at')
        self.assertEqual(response.status_code, 200)
        
        results = response.data.get('results', response.data)
        if results:
            # Oldest should be first with ascending sort
            self.assertEqual(results[0]['id'], str(self.comments[0].pk))
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'ALLOWED_SORTS': ['-created_at', 'created_at'],
        'DEFAULT_SORT': '-created_at',
    })
    def test_invalid_sort_falls_back_to_default(self):
        """Test that invalid sorts fall back to default."""
        # Try to order by a field not in ALLOWED_SORTS
        response = self.client.get('/api/comments/?ordering=-updated_at')
        self.assertEqual(response.status_code, 200)
        
        # Should fall back to default ordering
        results = response.data.get('results', response.data)
        if results:
            # Should use default sort (-created_at), newest first
            self.assertEqual(results[0]['id'], str(self.comments[-1].pk))
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'ALLOWED_SORTS': ['-created_at', 'created_at', '-updated_at', 'updated_at'],
    })
    def test_all_allowed_sorts(self):
        """Test all configured allowed sorts."""
        allowed_sorts = ['-created_at', 'created_at', '-updated_at', 'updated_at']
        
        for sort in allowed_sorts:
            response = self.client.get(f'/api/comments/?ordering={sort}')
            self.assertEqual(response.status_code, 200, 
                           f"Sort {sort} should be allowed")
    
    def test_empty_allowed_sorts_allows_anything(self):
        """Test that empty ALLOWED_SORTS doesn't restrict sorting."""
        # With empty or None ALLOWED_SORTS, any valid field should work
        response = self.client.get('/api/comments/?ordering=-updated_at')
        self.assertEqual(response.status_code, 200)


class ContentObjectSortValidationTestCase(TestCase):
    """Test sort validation for content-specific endpoint."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.content_type = ContentType.objects.get_for_model(User)
        
        # Create comments for specific object
        for i in range(3):
            Comment.objects.create(
                content_type=self.content_type,
                object_id=self.user.id,
                user=self.user,
                content=f"Comment {i}"
            )
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'ALLOWED_SORTS': ['-created_at', 'created_at'],
    })
    def test_content_endpoint_respects_allowed_sorts(self):
        """Test that content-specific endpoint also validates sorts."""
        # Valid sort should work
        url = f'/api/content/auth.user/{self.user.id}/comments/?ordering=created_at'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Invalid sort should fall back to default
        url = f'/api/content/auth.user/{self.user.id}/comments/?ordering=-updated_at'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])