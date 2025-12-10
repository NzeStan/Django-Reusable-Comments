"""
Pytest fixtures for django_comments tests.

Provides comprehensive fixtures for testing all aspects of the commenting system
including models, API endpoints, permissions, and complex scenarios.
"""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from rest_framework.test import APIClient, APIRequestFactory

from ..models import Comment, CommentFlag
from .factories import (
    AnonymousCommentFactory,
    CommentFactory,
    CommentFlagFactory,
    LongCommentFactory,
    OffensiveFlagFactory,
    PrivateCommentFactory,
    RemovedCommentFactory,
    ShortCommentFactory,
    SpamFlagFactory,
    SpecialCharCommentFactory,
    StaffUserFactory,
    SuperUserFactory,
    TestPostFactory,
    TestPostWithUUIDFactory,
    ThreadedCommentFactory,
    UnicodeCommentFactory,
    UserFactory,
    create_bulk_comments,
    create_comment_thread,
    create_comment_with_history,
    create_flagged_comment,
)

User = get_user_model()


# ============================================================================
# Database and Environment Setup
# ============================================================================

@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Set up the test database with any required initial data.
    """
    with django_db_blocker.unblock():
        # Create default groups
        Group.objects.get_or_create(name='Moderators')
        Group.objects.get_or_create(name='Commenters')


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Automatically enable database access for all tests.
    """
    pass


@pytest.fixture
def request_factory():
    """
    Return a Django RequestFactory instance.
    """
    return RequestFactory()


@pytest.fixture
def api_request_factory():
    """
    Return a DRF APIRequestFactory instance.
    """
    return APIRequestFactory()


# ============================================================================
# Client Fixtures
# ============================================================================

@pytest.fixture
def api_client():
    """
    Return an unauthenticated DRF API client.
    """
    return APIClient()


@pytest.fixture
def authenticated_client(user):
    """
    Return an API client authenticated as a regular user.
    """
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def staff_client(staff_user):
    """
    Return an API client authenticated as a staff user.
    """
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def superuser_client(superuser):
    """
    Return an API client authenticated as a superuser.
    """
    client = APIClient()
    client.force_authenticate(user=superuser)
    return client


@pytest.fixture
def moderator_client(moderator_user):
    """
    Return an API client authenticated as a moderator.
    """
    client = APIClient()
    client.force_authenticate(user=moderator_user)
    return client


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture
def user():
    """
    Return a regular user instance.
    """
    return UserFactory()


@pytest.fixture
def user2():
    """
    Return a second regular user for multi-user scenarios.
    """
    return UserFactory()


@pytest.fixture
def users():
    """
    Return a list of multiple users.
    """
    return [UserFactory() for _ in range(5)]


@pytest.fixture
def staff_user():
    """
    Return a staff user instance.
    """
    return StaffUserFactory()


@pytest.fixture
def superuser():
    """
    Return a superuser instance.
    """
    return SuperUserFactory()


@pytest.fixture
def moderator_user():
    """
    Return a user with comment moderation permissions.
    """
    user = UserFactory()
    moderator_group, _ = Group.objects.get_or_create(name='Moderators')
    
    # Add comment moderation permission
    content_type = ContentType.objects.get_for_model(Comment)
    permission, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename='can_moderate_comments',
        defaults={'name': 'Can moderate comments'}
    )
    moderator_group.permissions.add(permission)
    
    # Add user to group
    user.groups.add(moderator_group)
    user.refresh_from_db()
    
    return user


@pytest.fixture
def moderator_group():
    """
    Return the Moderators group with appropriate permissions.
    """
    group, _ = Group.objects.get_or_create(name='Moderators')
    
    content_type = ContentType.objects.get_for_model(Comment)
    permission, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename='can_moderate_comments',
        defaults={'name': 'Can moderate comments'}
    )
    group.permissions.add(permission)
    
    return group


# ============================================================================
# Content Fixtures (Posts)
# ============================================================================

@pytest.fixture
def test_post():
    """
    Return a test post instance with integer primary key.
    """
    return TestPostFactory()


@pytest.fixture
def test_posts():
    """
    Return multiple test posts for list/filtering scenarios.
    """
    return [TestPostFactory() for _ in range(5)]


@pytest.fixture
def test_post_with_uuid():
    """
    Return a test post with UUID primary key.
    """
    return TestPostWithUUIDFactory()


@pytest.fixture
def test_posts_with_uuid():
    """
    Return multiple test posts with UUID primary keys.
    """
    return [TestPostWithUUIDFactory() for _ in range(5)]


# ============================================================================
# Basic Comment Fixtures
# ============================================================================

@pytest.fixture
def comment(user, test_post):
    """
    Return a basic comment instance.
    """
    content_type = ContentType.objects.get_for_model(test_post)
    return CommentFactory(
        user=user,
        content_type=content_type,
        object_id=test_post.id
    )


@pytest.fixture
def comments(user, test_post):
    """
    Return multiple comments for the same post.
    """
    content_type = ContentType.objects.get_for_model(test_post)
    return [
        CommentFactory(
            user=user,
            content_type=content_type,
            object_id=test_post.id
        )
        for _ in range(5)
    ]


@pytest.fixture
def comment_on_uuid_post(user, test_post_with_uuid):
    """
    Return a comment on a post with UUID primary key.
    """
    content_type = ContentType.objects.get_for_model(test_post_with_uuid)
    return CommentFactory(
        user=user,
        content_type=content_type,
        object_id=str(test_post_with_uuid.id)
    )


@pytest.fixture
def anonymous_comment(test_post):
    """
    Return an anonymous comment (no user).
    """
    content_type = ContentType.objects.get_for_model(test_post)
    return AnonymousCommentFactory(
        content_type=content_type,
        object_id=test_post.id
    )


@pytest.fixture
def private_comment(user, test_post):
    """
    Return a private/unpublished comment.
    """
    content_type = ContentType.objects.get_for_model(test_post)
    return PrivateCommentFactory(
        user=user,
        content_type=content_type,
        object_id=test_post.id
    )


@pytest.fixture
def removed_comment(user, test_post):
    """
    Return a removed comment.
    """
    content_type = ContentType.objects.get_for_model(test_post)
    return RemovedCommentFactory(
        user=user,
        content_type=content_type,
        object_id=test_post.id
    )


# ============================================================================
# Edge Case Comment Fixtures
# ============================================================================

@pytest.fixture
def long_comment(user, test_post):
    """
    Return a comment with very long content.
    """
    content_type = ContentType.objects.get_for_model(test_post)
    return LongCommentFactory(
        user=user,
        content_type=content_type,
        object_id=test_post.id
    )


@pytest.fixture
def short_comment(user, test_post):
    """
    Return a comment with very short content.
    """
    content_type = ContentType.objects.get_for_model(test_post)
    return ShortCommentFactory(
        user=user,
        content_type=content_type,
        object_id=test_post.id
    )


@pytest.fixture
def special_char_comment(user, test_post):
    """
    Return a comment with special characters (XSS attempts, etc.).
    """
    content_type = ContentType.objects.get_for_model(test_post)
    return SpecialCharCommentFactory(
        user=user,
        content_type=content_type,
        object_id=test_post.id
    )


@pytest.fixture
def unicode_comment(user, test_post):
    """
    Return a comment with Unicode characters.
    """
    content_type = ContentType.objects.get_for_model(test_post)
    return UnicodeCommentFactory(
        user=user,
        content_type=content_type,
        object_id=test_post.id
    )


# ============================================================================
# Threaded Comment Fixtures
# ============================================================================

@pytest.fixture
def comment_with_parent(user, test_post, comment):
    """
    Return a child comment (reply to another comment).
    """
    content_type = ContentType.objects.get_for_model(test_post)
    return ThreadedCommentFactory(
        user=user,
        content_type=content_type,
        object_id=test_post.id,
        parent=comment
    )


@pytest.fixture
def comment_thread(user, test_post):
    """
    Return a complete comment thread (parent + children + grandchildren).
    
    Structure:
        - Parent (root)
            - Child 1
                - Grandchild 1
                - Grandchild 2
            - Child 2
            - Child 3
    """
    content_type = ContentType.objects.get_for_model(test_post)
    
    # Create parent comment
    parent = CommentFactory(
        user=user,
        content_type=content_type,
        object_id=test_post.id,
        parent=None
    )
    
    # Create child comments
    children = [
        CommentFactory(
            user=user,
            content_type=content_type,
            object_id=test_post.id,
            parent=parent
        )
        for _ in range(3)
    ]
    
    # Create grandchildren for first child
    grandchildren = [
        CommentFactory(
            user=user,
            content_type=content_type,
            object_id=test_post.id,
            parent=children[0]
        )
        for _ in range(2)
    ]
    
    return {
        'parent': parent,
        'children': children,
        'grandchildren': grandchildren,
        'all_comments': [parent] + children + grandchildren
    }


@pytest.fixture
def deep_comment_thread(user, test_post):
    """
    Return a deep comment thread (5 levels).
    """
    return create_comment_thread(
        depth=5,
        width=2,
        post=test_post,
        user=user
    )


@pytest.fixture
def wide_comment_thread(user, test_post):
    """
    Return a wide comment thread (many siblings).
    """
    return create_comment_thread(
        depth=2,
        width=10,
        post=test_post,
        user=user
    )


# ============================================================================
# Flag Fixtures
# ============================================================================

@pytest.fixture
def comment_flag(user, comment):
    """
    Return a single comment flag.
    """
    return CommentFlagFactory(
        comment=comment,
        user=user
    )


@pytest.fixture
def spam_flag(user, comment):
    """
    Return a spam flag.
    """
    return SpamFlagFactory(
        comment=comment,
        user=user
    )


@pytest.fixture
def offensive_flag(user, comment):
    """
    Return an offensive content flag.
    """
    return OffensiveFlagFactory(
        comment=comment,
        user=user
    )


@pytest.fixture
def flagged_comment(test_post):
    """
    Return a comment with multiple flags from different users.
    """
    return create_flagged_comment(flag_count=3)


@pytest.fixture
def heavily_flagged_comment(test_post):
    """
    Return a comment with many flags (>10).
    """
    return create_flagged_comment(flag_count=15)


# ============================================================================
# Complex Scenario Fixtures
# ============================================================================

@pytest.fixture
def comment_with_history(user, test_post):
    """
    Return a comment that has been edited multiple times.
    """
    content_type = ContentType.objects.get_for_model(test_post)
    comment = CommentFactory(
        user=user,
        content_type=content_type,
        object_id=test_post.id
    )
    return create_comment_with_history(versions=5)


@pytest.fixture
def bulk_comments(test_post):
    """
    Return a large number of comments for performance testing.
    """
    return create_bulk_comments(count=100, post=test_post)


@pytest.fixture
def multi_user_comments(users, test_post):
    """
    Return comments from multiple different users.
    """
    content_type = ContentType.objects.get_for_model(test_post)
    return [
        CommentFactory(
            user=user,
            content_type=content_type,
            object_id=test_post.id
        )
        for user in users
    ]


@pytest.fixture
def mixed_status_comments(user, test_post):
    """
    Return comments with various statuses (public, private, removed).
    """
    content_type = ContentType.objects.get_for_model(test_post)
    
    return {
        'public': CommentFactory(
            user=user,
            content_type=content_type,
            object_id=test_post.id,
            is_public=True,
            is_removed=False
        ),
        'private': PrivateCommentFactory(
            user=user,
            content_type=content_type,
            object_id=test_post.id
        ),
        'removed': RemovedCommentFactory(
            user=user,
            content_type=content_type,
            object_id=test_post.id
        )
    }


@pytest.fixture
def comments_across_posts(user, test_posts):
    """
    Return comments spread across multiple posts.
    """
    comments = []
    for post in test_posts:
        content_type = ContentType.objects.get_for_model(post)
        for _ in range(3):
            comments.append(
                CommentFactory(
                    user=user,
                    content_type=content_type,
                    object_id=post.id
                )
            )
    return comments


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture
def content_type_for_post():
    """
    Return the ContentType for TestPost model.
    """
    return ContentType.objects.get_for_model(TestPost)


@pytest.fixture
def content_type_for_uuid_post():
    """
    Return the ContentType for TestPostWithUUID model.
    """
    return ContentType.objects.get_for_model(TestPostWithUUID)


@pytest.fixture
def sample_comment_data(user, test_post):
    """
    Return sample data dict for creating a comment via API.
    """
    content_type = ContentType.objects.get_for_model(test_post)
    return {
        'content': 'This is a test comment via API',
        'content_type': content_type.id,
        'object_id': str(test_post.id),
        'user': user.id
    }


@pytest.fixture
def sample_flag_data(comment, user):
    """
    Return sample data dict for creating a flag via API.
    """
    return {
        'comment': str(comment.id),
        'user': user.id,
        'flag': 'spam',
        'reason': 'This looks like spam content'
    }


# ============================================================================
# Performance Testing Fixtures
# ============================================================================

@pytest.fixture
def large_thread(test_post):
    """
    Return a very large comment thread for performance testing.
    """
    return create_comment_thread(
        depth=10,
        width=3,
        post=test_post
    )


@pytest.fixture
def many_posts_with_comments():
    """
    Return many posts with comments for testing queries.
    """
    posts = [TestPostFactory() for _ in range(20)]
    for post in posts:
        create_bulk_comments(count=50, post=post, randomize=False)
    return posts