"""
Factories for creating test data with real-world scenarios.

This module provides comprehensive factories for testing django-reusable-comments
with realistic data including edge cases, special characters, and various user types.
"""
import uuid
from datetime import timedelta

import factory
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from factory import fuzzy
from factory.django import DjangoModelFactory

from ..models import Comment, CommentFlag
from .models import TestPost, TestPostWithUUID

User = get_user_model()


class UserFactory(DjangoModelFactory):
    """
    Factory for creating User instances with realistic data.
    """
    
    username = factory.Sequence(lambda n: f'user_{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_active = True
    is_staff = False
    is_superuser = False
    date_joined = factory.LazyFunction(
        lambda: timezone.now() - timedelta(days=fuzzy.FuzzyInteger(1, 365).fuzz())
    )
    
    class Meta:
        model = User
        django_get_or_create = ('username',)
        skip_postgeneration_save = True


class StaffUserFactory(UserFactory):
    """Factory for staff users."""
    is_staff = True


class SuperUserFactory(UserFactory):
    """Factory for superusers."""
    is_staff = True
    is_superuser = True


class TestPostFactory(DjangoModelFactory):
    """
    Factory for creating TestPost instances with realistic content.
    """
    
    title = factory.Faker(
        'sentence',
        nb_words=6,
        variable_nb_words=True
    )
    created_at = factory.LazyFunction(
        lambda: timezone.now() - timedelta(days=fuzzy.FuzzyInteger(1, 30).fuzz())
    )
    
    class Meta:
        model = TestPost
    
    @factory.lazy_attribute
    def content(self):
        """Generate realistic post content."""
        from faker import Faker
        fake = Faker()
        paragraphs = [fake.paragraph() for _ in range(3)]
        return '\n\n'.join(paragraphs)


class TestPostWithUUIDFactory(DjangoModelFactory):
    """
    Factory for creating TestPostWithUUID instances.
    """
    
    title = factory.Faker(
        'sentence',
        nb_words=6,
        variable_nb_words=True
    )
    created_at = factory.LazyFunction(
        lambda: timezone.now() - timedelta(days=fuzzy.FuzzyInteger(1, 30).fuzz())
    )
    
    class Meta:
        model = TestPostWithUUID
    
    @factory.lazy_attribute
    def content(self):
        """Generate realistic post content."""
        from faker import Faker
        fake = Faker()
        paragraphs = [fake.paragraph() for _ in range(3)]
        return '\n\n'.join(paragraphs)


class CommentFactory(DjangoModelFactory):
    """
    Factory for creating Comment instances with realistic content.
    
    NOTE: Does NOT include user_url, ip_address, user_agent, submit_date, or level
    as these fields don't exist in the Comment model.
    """
    
    content = factory.Faker(
        'paragraph',
        nb_sentences=3
    )
    user = factory.SubFactory(UserFactory)
    user_name = factory.LazyAttribute(lambda obj: obj.user.username if obj.user else '')
    user_email = factory.LazyAttribute(lambda obj: obj.user.email if obj.user else '')
    
    # Status fields
    is_public = True
    is_removed = False
    
    # By default, create a comment for a TestPost
    content_type = factory.LazyAttribute(
        lambda _: ContentType.objects.get_for_model(TestPost)
    )
    object_id = factory.LazyAttribute(
        lambda o: str(TestPostFactory.create().id)
    )
    
    parent = None
    
    class Meta:
        model = Comment


class AnonymousCommentFactory(CommentFactory):
    """Factory for anonymous comments (no user)."""
    user = None
    user_name = factory.Faker('name')
    user_email = factory.Faker('email')


class LongCommentFactory(CommentFactory):
    """Factory for very long comments."""
    
    @factory.lazy_attribute
    def content(self):
        from faker import Faker
        fake = Faker()
        paragraphs = [fake.paragraph() for _ in range(10)]
        return '\n\n'.join(paragraphs)


class ShortCommentFactory(CommentFactory):
    """Factory for short comments."""
    content = factory.Faker('sentence')


class SpecialCharCommentFactory(CommentFactory):
    """Factory for comments with HTML/JS special characters."""
    content = "<script>alert('XSS')</script> & special chars: <>&\"'"


class UnicodeCommentFactory(CommentFactory):
    """Factory for comments with Unicode characters."""
    content = "Hello 世界 مرحبا العالم 안녕하세요 😀🎉🌟"


class RemovedCommentFactory(CommentFactory):
    """Factory for removed comments."""
    is_removed = True
    is_public = False


class PrivateCommentFactory(CommentFactory):
    """Factory for private (unpublished) comments."""
    is_public = False


class ThreadedCommentFactory(CommentFactory):
    """
    Factory for creating threaded comments.
    
    Usage:
        parent = CommentFactory()
        child = ThreadedCommentFactory(parent=parent)
    """
    parent = factory.SubFactory(CommentFactory)


class CommentFlagFactory(DjangoModelFactory):
    """
    Factory for creating CommentFlag instances.
    """
    
    comment = factory.SubFactory(CommentFactory)
    user = factory.SubFactory(UserFactory)
    flag = fuzzy.FuzzyChoice(['spam', 'inappropriate', 'offensive', 'other'])
    reason = factory.Faker('sentence')
    
    class Meta:
        model = CommentFlag


class SpamFlagFactory(CommentFlagFactory):
    """Factory for spam flags."""
    flag = 'spam'
    reason = "This comment is spam"


class OffensiveFlagFactory(CommentFlagFactory):
    """Factory for offensive flags."""
    flag = 'offensive'
    reason = "This comment is offensive"


# ============================================================================
# Utility Functions for Creating Complex Test Scenarios
# ============================================================================

def create_comment_thread(depth=3, width=2, parent=None, content_object=None):
    """
    Create a tree of comments with specified depth and width.
    
    Args:
        depth: How deep the thread goes (max 3 due to model constraints)
        width: How many children per parent
        parent: Parent comment (None for root)
        content_object: Object to comment on
    
    Returns:
        list: All created comments
    """
    comments = []
    
    if depth <= 0:
        return comments
    
    # Limit depth to 3 (model constraint)
    depth = min(depth, 3)
    
    if parent is None and content_object is None:
        content_object = TestPostFactory()
    
    for _ in range(width):
        if parent:
            comment = CommentFactory(
                parent=parent,
                content_type=parent.content_type,
                object_id=parent.object_id
            )
        else:
            ct = ContentType.objects.get_for_model(content_object)
            comment = CommentFactory(
                content_type=ct,
                object_id=str(content_object.pk)
            )
        
        comments.append(comment)
        
        if depth > 1:
            children = create_comment_thread(
                depth=depth - 1,
                width=width,
                parent=comment
            )
            comments.extend(children)
    
    return comments


def create_flagged_comment(flag_count=3):
    """
    Create a comment with multiple flags from different users.
    
    Args:
        flag_count: Number of flags to create
    
    Returns:
        tuple: (comment, list of flags)
    """
    comment = CommentFactory()
    flags = []
    
    for _ in range(flag_count):
        flag = CommentFlagFactory(comment=comment)
        flags.append(flag)
    
    return comment, flags


def create_comment_with_history(versions=5):
    """
    Create a comment and simulate version history (for testing).
    
    Args:
        versions: Number of versions to simulate
    
    Returns:
        Comment: The comment with simulated history
    """
    comment = CommentFactory()
    # In real implementation, you might track versions
    # This is just a placeholder for testing
    return comment


def create_bulk_comments(count=100, content_object=None):
    """
    Create bulk comments for performance testing.
    
    Args:
        count: Number of comments to create
        content_object: Object to comment on
    
    Returns:
        list: All created comments
    """
    if content_object is None:
        content_object = TestPostFactory()
    
    ct = ContentType.objects.get_for_model(content_object)
    
    return [
        CommentFactory(
            content_type=ct,
            object_id=str(content_object.pk)
        )
        for _ in range(count)
    ]