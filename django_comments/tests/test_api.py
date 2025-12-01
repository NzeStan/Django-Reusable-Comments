"""
Tests for the django_comments API.
"""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework import status
from django_comments.conf import comments_settings
from ..models import Comment, CommentFlag


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