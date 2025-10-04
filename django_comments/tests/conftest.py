"""
Pytest fixtures for django_comments tests.
"""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from ..models import Comment
from .factories import (
    UserFactory, TestPostFactory, TestPostWithUUIDFactory,
    CommentFactory, CommentFlagFactory
)

User = get_user_model()


@pytest.fixture
def api_client():
    """
    Return a DRF API client.
    """
    return APIClient()


@pytest.fixture
def user():
    """
    Return a regular user.
    """
    return UserFactory()


@pytest.fixture
def staff_user():
    """
    Return a staff user.
    """
    user = UserFactory(is_staff=True)
    return user


@pytest.fixture
def moderator_user():
    """
    Return a user with comment moderation permissions.
    """
    user = UserFactory()
    moderator_group, _ = Group.objects.get_or_create(name='Moderators')
    
    # Add comment moderation permission
    content_type = ContentType.objects.get_for_model(Comment)
    permission = Permission.objects.get(
        content_type=content_type,
        codename='can_moderate_comments'
    )
    moderator_group.permissions.add(permission)
    
    # Add user to group
    user.groups.add(moderator_group)
    
    return user


@pytest.fixture
def authenticated_client(user):
    """
    Return an authenticated API client.
    """
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def staff_client(staff_user):
    """
    Return an API client authenticated as staff user.
    """
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def moderator_client(moderator_user):
    """
    Return an API client authenticated as moderator user.
    """
    client = APIClient()
    client.force_authenticate(user=moderator_user)
    return client


@pytest.fixture
def test_post():
    """
    Return a test post instance.
    """
    return TestPostFactory()


@pytest.fixture
def test_post_with_uuid():
    """
    Return a test post with UUID instance.
    """
    return TestPostWithUUIDFactory()


@pytest.fixture
def comment(user, test_post):
    """
    Return a comment instance.
    """
    return CommentFactory(
        user=user,
        content_type=ContentType.objects.get_for_model(test_post),
        object_id=test_post.id
    )


@pytest.fixture
def comment_thread(user, test_post):
    """
    Return a thread of comments (parent + children).
    """
    # Create parent comment
    parent = CommentFactory(
        user=user,
        content_type=ContentType.objects.get_for_model(test_post),
        object_id=test_post.id
    )
    
    # Create child comments
    children = [
        CommentFactory(
            user=user,
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            parent=parent
        )
        for _ in range(3)
    ]
    
    # Create grandchild comment
    grandchild = CommentFactory(
        user=user,
        content_type=ContentType.objects.get_for_model(test_post),
        object_id=test_post.id,
        parent=children[0]
    )
    
    return {
        'parent': parent,
        'children': children,
        'grandchild': grandchild
    }


@pytest.fixture
def flagged_comment(user, test_post):
    """
    Return a flagged comment instance.
    """
    comment = CommentFactory(
        user=user,
        content_type=ContentType.objects.get_for_model(test_post),
        object_id=test_post.id
    )
    
    # Create flags from different users
    flags = [
        CommentFlagFactory(
            comment=comment,
            user=UserFactory()
        )
        for _ in range(2)
    ]
    
    return comment