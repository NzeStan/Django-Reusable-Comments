"""
Tests for the django_comments API.
"""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework import status
from django_comments.conf import comments_settings
from ..models import Comment, CommentFlag
import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework import status

from ..models import Comment
from .factories import CommentFactory, UserFactory
from .models import TestPost, TestPostWithUUID


@pytest.mark.django_db
class TestCommentListAPI:
    """Tests for the comment list API endpoint."""
    
    def test_list_comments_anonymous(self, api_client, comment):
        """Test listing comments as anonymous user."""
        url = reverse('django_comments_api:comment-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        
    def test_list_comments_authenticated(self, authenticated_client, comment):
        """Test listing comments as authenticated user."""
        url = reverse('django_comments_api:comment-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        
    def test_list_comments_with_filtering(self, api_client, comment, test_post):
        """Test filtering comments by content object."""
        url = reverse('django_comments_api:comment-list')
        content_type = ContentType.objects.get_for_model(test_post)
        
        # Filter by content type and object ID
        response = api_client.get(
            url,
            {'content_type': f"{content_type.app_label}.{content_type.model}", 
             'object_id': test_post.id}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        
        # Filter by non-existent content type
        response = api_client.get(
            url,
            {'content_type': 'nonexistent.model'}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 0
        
    def test_list_comments_for_specific_object(self, api_client, comment, test_post):
        """Test listing comments for a specific object using the dedicated endpoint."""
        content_type = ContentType.objects.get_for_model(test_post)
        url = reverse(
            'django_comments_api:content-object-comments',
            kwargs={
                'content_type': f"{content_type.app_label}.{content_type.model}",
                'object_id': test_post.id
            }
        )
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == comment.id  # ← This fixes the type mismatch

        

@pytest.mark.django_db
class TestCommentCreateAPI:
    """Tests for the comment creation API endpoint."""
    
    def test_create_comment_anonymous(self, api_client, test_post):
        """Test creating a comment as anonymous user."""
        url = reverse('django_comments_api:comment-list')
        content_type = ContentType.objects.get_for_model(test_post)
        
        data = {
            'content': 'This is a test comment from anonymous.',
            'content_type': f"{content_type.app_label}.{content_type.model}",
            'object_id': test_post.id,
            'user_name': 'Anonymous User',
            'user_email': 'anonymous@example.com'  # Add this line
        }
        
        response = api_client.post(url, data, format='json')
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        assert response.status_code == status.HTTP_201_CREATED
        assert Comment.objects.count() == 1
        assert Comment.objects.first().user is None
        assert Comment.objects.first().user_name == 'Anonymous User'

    def test_create_comment_authenticated(self, authenticated_client, user, test_post):
        """Test creating a comment as authenticated user."""
        url = reverse('django_comments_api:comment-list')
        content_type = ContentType.objects.get_for_model(test_post)
        
        data = {
            'content': 'This is a test comment from authenticated user.',
            'content_type': f"{content_type.app_label}.{content_type.model}",
            'object_id': test_post.id
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Comment.objects.count() == 1
        assert Comment.objects.first().user == user
        
    def test_create_comment_with_parent(self, authenticated_client, comment, test_post):
        """Test creating a reply to an existing comment."""
        url = reverse('django_comments_api:comment-list')
        content_type = ContentType.objects.get_for_model(test_post)
        
        data = {
            'content': 'This is a reply to the existing comment.',
            'content_type': f"{content_type.app_label}.{content_type.model}",
            'object_id': test_post.id,
            'parent': comment.id
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Comment.objects.count() == 2
        
        # Check thread relationship
        child_comment = Comment.objects.exclude(id=comment.id).first()
        assert child_comment.parent == comment
        assert child_comment.thread_id == str(comment.id)
        

@pytest.mark.django_db
class TestCommentUpdateDeleteAPI:
    """Tests for the comment update and delete API endpoints."""
    
    def test_update_comment_owner(self, authenticated_client, comment):
        """Test updating a comment as the owner."""
        url = reverse('django_comments_api:comment-detail', args=[comment.id])
        
        data = {
            'content': 'Updated comment content.'
        }
        
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        comment.refresh_from_db()
        assert comment.content == 'Updated comment content.'
        
    def test_update_comment_not_owner(self, api_client, comment):
        """Test updating a comment as a non-owner."""
        url = reverse('django_comments_api:comment-detail', args=[comment.id])
        
        data = {
            'content': 'Unauthorized update attempt.'
        }
        
        response = api_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        comment.refresh_from_db()
        assert comment.content != 'Unauthorized update attempt.'
        
    def test_delete_comment_owner(self, authenticated_client, comment):
        """Test deleting a comment as the owner."""
        url = reverse('django_comments_api:comment-detail', args=[comment.id])
        
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Comment.objects.count() == 0
        
    def test_delete_comment_not_owner(self, api_client, comment):
        """Test deleting a comment as a non-owner."""
        url = reverse('django_comments_api:comment-detail', args=[comment.id])
        
        response = api_client.delete(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Comment.objects.count() == 1
        
    def test_delete_comment_staff(self, staff_client, comment):
        """Test deleting a comment as a staff user."""
        url = reverse('django_comments_api:comment-detail', args=[comment.id])
        
        response = staff_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Comment.objects.count() == 0


@pytest.mark.django_db
class TestCommentModerationAPI:
    """Tests for the comment moderation API endpoints."""
    
    def test_flag_comment(self, authenticated_client, comment):
        """Test flagging a comment."""
        url = reverse('django_comments_api:comment-flag', args=[comment.id])
        
        data = {
            'flag_type': 'spam',
            'reason': 'This is a spam comment.'
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert CommentFlag.objects.count() == 1
        assert CommentFlag.objects.first().flag == 'spam'
        assert CommentFlag.objects.first().reason == 'This is a spam comment.'
        
    def test_flag_comment_anonymous(self, api_client, comment):
        """Test flagging a comment as anonymous user."""
        url = reverse('django_comments_api:comment-flag', args=[comment.id])
        
        data = {
            'flag_type': 'spam',
            'reason': 'This is a spam comment.'
        }
        
        response = api_client.post(url, data, format='json')
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert CommentFlag.objects.count() == 0
        
    def test_approve_comment_moderator(self, moderator_client, comment):
        """Test approving a comment as a moderator."""
        # First make the comment non-public
        comment.is_public = False
        comment.save()
        
        url = reverse('django_comments_api:comment-approve', args=[comment.id])
        
        response = moderator_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        comment.refresh_from_db()
        assert comment.is_public is True
        
    def test_approve_comment_not_moderator(self, authenticated_client, comment):
        """Test approving a comment as a non-moderator."""
        # First make the comment non-public
        comment.is_public = False
        comment.save()
        
        url = reverse('django_comments_api:comment-approve', args=[comment.id])
        
        response = authenticated_client.post(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        comment.refresh_from_db()
        assert comment.is_public is False
        
    def test_reject_comment_moderator(self, moderator_client, comment):
        """Test rejecting a comment as a moderator."""
        url = reverse('django_comments_api:comment-reject', args=[comment.id])
        
        response = moderator_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        comment.refresh_from_db()
        assert comment.is_public is False
        
    def test_reject_comment_not_moderator(self, authenticated_client, comment):
        """Test rejecting a comment as a non-moderator."""
        url = reverse('django_comments_api:comment-reject', args=[comment.id])
        
        response = authenticated_client.post(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        comment.refresh_from_db()
        assert comment.is_public is True

@pytest.mark.django_db
class TestCommentPagination:
    """Tests for comment list pagination."""
    
    def test_pagination_first_page(self, api_client, user, test_post):
        """Test first page of paginated results."""
        # Create 25 comments (page size is 10 in test settings)
        for i in range(25):
            CommentFactory(
                content_type=ContentType.objects.get_for_model(test_post),
                object_id=test_post.id,
                user=user,
                content=f'Comment {i}'
            )
        
        url = reverse('django_comments_api:comment-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 25
        assert len(response.data['results']) == 10
        assert response.data['next'] is not None
        assert response.data['previous'] is None
    
    def test_pagination_second_page(self, api_client, user, test_post):
        """Test second page of paginated results."""
        # Create 25 comments
        for i in range(25):
            CommentFactory(
                content_type=ContentType.objects.get_for_model(test_post),
                object_id=test_post.id,
                user=user,
                content=f'Comment {i}'
            )
        
        url = reverse('django_comments_api:comment-list')
        response = api_client.get(url, {'page': 2})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 10
        assert response.data['next'] is not None
        assert response.data['previous'] is not None
    
    def test_pagination_last_page(self, api_client, user, test_post):
        """Test last page of paginated results."""
        # Create 25 comments
        for i in range(25):
            CommentFactory(
                content_type=ContentType.objects.get_for_model(test_post),
                object_id=test_post.id,
                user=user,
                content=f'Comment {i}'
            )
        
        url = reverse('django_comments_api:comment-list')
        response = api_client.get(url, {'page': 3})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 5  # Only 5 on last page
        assert response.data['next'] is None
        assert response.data['previous'] is not None


@pytest.mark.django_db
class TestCommentSearch:
    """Tests for comment search functionality."""
    
    def test_search_by_content(self, api_client, user, test_post):
        """Test searching comments by content."""
        # Create comments with specific content
        searchable = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            content='This comment contains the unique-term-12345'
        )
        
        other = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            content='This is a normal comment'
        )
        
        url = reverse('django_comments_api:comment-list')
        response = api_client.get(url, {'search': 'unique-term-12345'})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == searchable.id
    
    def test_search_by_user_name(self, api_client, test_post):
        """Test searching comments by user name."""
        user_with_unique_name = UserFactory(username='uniqueuser999')
        common_user = UserFactory(username='commonuser')
        
        searchable = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user_with_unique_name,
            content='Regular content'
        )
        
        other = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=common_user,
            content='Regular content'
        )
        
        url = reverse('django_comments_api:comment-list')
        response = api_client.get(url, {'search': 'uniqueuser999'})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == searchable.id
    
    def test_search_returns_empty_when_no_match(self, api_client, comment):
        """Test search returns empty results when no match."""
        url = reverse('django_comments_api:comment-list')
        response = api_client.get(url, {'search': 'nonexistent-search-term-xyz'})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 0


@pytest.mark.django_db
class TestCommentOrdering:
    """Tests for comment ordering."""
    
    def test_order_by_created_at_desc(self, api_client, user, test_post):
        """Test ordering by created_at descending (newest first)."""
        import time
        
        # Create comments with slight time difference
        comment1 = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            content='First comment'
        )
        time.sleep(0.01)
        
        comment2 = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            content='Second comment'
        )
        time.sleep(0.01)
        
        comment3 = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            content='Third comment'
        )
        
        url = reverse('django_comments_api:comment-list')
        response = api_client.get(url, {'ordering': '-created_at'})
        
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        
        # Newest first
        assert results[0]['id'] == comment3.id
        assert results[1]['id'] == comment2.id
        assert results[2]['id'] == comment1.id
    
    def test_order_by_created_at_asc(self, api_client, user, test_post):
        """Test ordering by created_at ascending (oldest first)."""
        import time
        
        comment1 = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            content='First comment'
        )
        time.sleep(0.01)
        
        comment2 = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            content='Second comment'
        )
        time.sleep(0.01)
        
        comment3 = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            content='Third comment'
        )
        
        url = reverse('django_comments_api:comment-list')
        response = api_client.get(url, {'ordering': 'created_at'})
        
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        
        # Oldest first
        assert results[0]['id'] == comment1.id
        assert results[1]['id'] == comment2.id
        assert results[2]['id'] == comment3.id


@pytest.mark.django_db
class TestCommentValidation:
    """Tests for comment validation and edge cases."""
    
    def test_create_comment_max_length_exceeded(self, authenticated_client, test_post, monkeypatch):
        """Test that comments exceeding max length are rejected."""
        from ..conf import comments_settings
        monkeypatch.setattr(comments_settings, 'MAX_COMMENT_LENGTH', 100)
        
        url = reverse('django_comments_api:comment-list')
        content_type = ContentType.objects.get_for_model(test_post)
        
        # Create content longer than max length
        long_content = 'a' * 101
        
        data = {
            'content': long_content,
            'content_type': f"{content_type.app_label}.{content_type.model}",
            'object_id': test_post.id
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'content' in response.data or 'detail' in response.data
    
    def test_create_comment_max_depth_exceeded(self, authenticated_client, comment_thread, monkeypatch):
        """Test that comments exceeding max depth are rejected."""
        from ..conf import comments_settings
        monkeypatch.setattr(comments_settings, 'MAX_COMMENT_DEPTH', 2)
        
        # Get a comment at depth 2 (grandchild)
        grandchild = comment_thread['grandchild']
        
        url = reverse('django_comments_api:comment-list')
        content_type = grandchild.content_type
        
        # Try to create a comment deeper than max depth
        data = {
            'content': 'Too deep comment',
            'content_type': f"{content_type.app_label}.{content_type.model}",
            'object_id': grandchild.object_id,
            'parent': grandchild.id
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_create_comment_invalid_content_type_format(self, authenticated_client, test_post):
        """Test that invalid content type format is rejected."""
        url = reverse('django_comments_api:comment-list')
        
        data = {
            'content': 'Test comment',
            'content_type': 'invalid_format',  # Missing dot separator
            'object_id': test_post.id
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'content_type' in response.data
    
    def test_create_comment_for_non_commentable_model(self, authenticated_client, test_post, monkeypatch):
        """Test that comments on non-commentable models are rejected."""
        from ..conf import comments_settings
        # Set commentable models to empty list
        monkeypatch.setattr(comments_settings, 'COMMENTABLE_MODELS', [])
        
        url = reverse('django_comments_api:comment-list')
        content_type = ContentType.objects.get_for_model(test_post)
        
        data = {
            'content': 'Test comment',
            'content_type': f"{content_type.app_label}.{content_type.model}",
            'object_id': test_post.id
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestCommentWithUUID:
    """Tests for comments on models with UUID primary keys."""
    
    def test_create_comment_for_uuid_object(self, authenticated_client, test_post_with_uuid):
        """Test creating comment on object with UUID pk."""
        url = reverse('django_comments_api:comment-list')
        content_type = ContentType.objects.get_for_model(test_post_with_uuid)
        
        data = {
            'content': 'Comment on UUID object',
            'content_type': f"{content_type.app_label}.{content_type.model}",
            'object_id': str(test_post_with_uuid.id)  # UUID as string
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify comment was created correctly
        comment = Comment.objects.get(pk=response.data['id'])
        assert str(comment.object_id) == str(test_post_with_uuid.id)
        assert comment.content_object == test_post_with_uuid
    
    def test_list_comments_for_uuid_object(self, api_client, test_post_with_uuid, user):
        """Test listing comments for object with UUID pk."""
        # Create comment
        comment = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post_with_uuid),
            object_id=test_post_with_uuid.id,
            user=user
        )
        
        content_type = ContentType.objects.get_for_model(test_post_with_uuid)
        url = reverse(
            'django_comments_api:content-object-comments',
            kwargs={
                'content_type': f"{content_type.app_label}.{content_type.model}",
                'object_id': str(test_post_with_uuid.id)
            }
        )
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == comment.id


@pytest.mark.django_db
class TestCommentFiltering:
    """Tests for comment filtering."""
    
    def test_filter_by_is_public(self, api_client, user, test_post):
        """Test filtering by is_public status."""
        public_comment = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            is_public=True
        )
        
        non_public = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            is_public=False
        )
        
        url = reverse('django_comments_api:comment-list')
        response = api_client.get(url, {'is_public': 'true'})
        
        assert response.status_code == status.HTTP_200_OK
        # Anonymous users can only see public comments anyway
        assert len(response.data['results']) >= 1
    
    def test_filter_by_user(self, api_client, test_post):
        """Test filtering by user."""
        user1 = UserFactory()
        user2 = UserFactory()
        
        comment1 = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user1
        )
        
        comment2 = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user2
        )
        
        url = reverse('django_comments_api:comment-list')
        response = api_client.get(url, {'user': user1.id})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) >= 1
        assert all(c['user_info']['id'] == user1.id for c in response.data['results'])
    
    def test_filter_by_date_range(self, api_client, user, test_post):
        """Test filtering by date range."""
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        # Create comment
        comment = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user
        )
        
        # Get comments created after yesterday
        yesterday = (timezone.now() - timedelta(days=1)).isoformat()
        
        url = reverse('django_comments_api:comment-list')
        response = api_client.get(url, {'created_after': yesterday})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) >= 1
