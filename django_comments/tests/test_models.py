"""
Comprehensive tests for django_comments models.

Tests cover:
- Comment model creation, validation, and behavior
- CommentFlag model creation and validation  
- Threading and hierarchical structures
- Edge cases and real-world scenarios
- Success and failure paths

Run with: pytest django_comments/tests/test_models.py -v
Run specific: pytest django_comments/tests/test_models.py::TestCommentCreation -v
Run with markers: pytest -m models -v
"""
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from django_comments.models import Comment, CommentFlag
from django_comments.tests.factories import (
    CommentFactory,
    CommentFlagFactory,
    UserFactory,
)

User = get_user_model()


# ============================================================================
# COMMENT MODEL TESTS - BASIC CREATION
# ============================================================================

@pytest.mark.models
@pytest.mark.unit
class TestCommentCreation:
    """Test basic comment creation with various scenarios."""
    
    def test_create_comment_on_integer_pk_post(self, user, test_post):
        """Test creating a comment on a model with integer primary key."""
        content_type = ContentType.objects.get_for_model(test_post)
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content="This is a test comment"
        )
        
        assert comment.pk is not None
        assert isinstance(comment.id, uuid.UUID)
        assert comment.content == "This is a test comment"
        assert comment.user == user
        assert comment.content_type == content_type
        assert comment.object_id == str(test_post.id)
        assert comment.content_object == test_post
        assert comment.is_public is True
        assert comment.is_removed is False
    
    def test_create_comment_on_uuid_pk_post(self, user, test_post_with_uuid):
        """Test creating a comment on a model with UUID primary key."""
        content_type = ContentType.objects.get_for_model(test_post_with_uuid)
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post_with_uuid.id),
            user=user,
            content="Comment on UUID post"
        )
        
        assert comment.pk is not None
        assert isinstance(comment.id, uuid.UUID)
        assert comment.object_id == str(test_post_with_uuid.id)
        assert comment.content_object == test_post_with_uuid
    
    def test_create_comment_using_factory(self, user, test_post):
        """Test creating a comment using factory."""
        content_type = ContentType.objects.get_for_model(test_post)
        comment = CommentFactory(
            user=user,
            content_type=content_type,
            object_id=test_post.id
        )
        
        assert comment.pk is not None
        assert comment.user == user
        assert comment.content_object == test_post
        assert comment.path
        assert comment.thread_id
    
    def test_comment_auto_fields(self, user, test_post):
        """Test that auto fields are set correctly."""
        content_type = ContentType.objects.get_for_model(test_post)
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content="Test auto fields"
        )
        
        # Check timestamps
        assert comment.submit_date is not None
        assert comment.submit_date <= timezone.now()
        
        # Check UUID is generated
        assert isinstance(comment.id, uuid.UUID)
        
        # Check threading fields for root comment
        assert comment.path == str(comment.id)
        assert comment.thread_id == str(comment.id)
        assert comment.level == 0
        assert comment.parent is None
    
    def test_multiple_comments_same_post(self, users, test_post):
        """Test creating multiple comments on the same post."""
        content_type = ContentType.objects.get_for_model(test_post)
        comments = []
        
        for user in users:
            comment = Comment.objects.create(
                content_type=content_type,
                object_id=str(test_post.id),
                user=user,
                content=f"Comment by {user.username}"
            )
            comments.append(comment)
        
        assert len(comments) == len(users)
        assert Comment.objects.filter(
            content_type=content_type,
            object_id=str(test_post.id)
        ).count() == len(users)
        
        # Each comment should have unique ID
        comment_ids = [c.id for c in comments]
        assert len(comment_ids) == len(set(comment_ids))


# ============================================================================
# COMMENT MODEL TESTS - FIELD VALIDATION
# ============================================================================

@pytest.mark.models
@pytest.mark.unit
class TestCommentValidation:
    """Test comment field validation and constraints."""
    
    def test_comment_requires_content(self, user, test_post):
        """Test that content field is required."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        with pytest.raises((ValidationError, IntegrityError)):
            comment = Comment(
                content_type=content_type,
                object_id=str(test_post.id),
                user=user,
                content=""
            )
            comment.full_clean()
    
    def test_comment_requires_content_type(self, user):
        """Test that content_type field is required."""
        with pytest.raises((ValidationError, IntegrityError)):
            comment = Comment(
                object_id="1",
                user=user,
                content="Test content"
            )
            comment.save()
    
    def test_comment_requires_object_id(self, user, test_post):
        """Test that object_id field is required."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        with pytest.raises((ValidationError, IntegrityError)):
            comment = Comment(
                content_type=content_type,
                user=user,
                content="Test content"
            )
            comment.save()
    
    def test_empty_content_validation(self, user, test_post):
        """Test that empty content fails validation."""
        content_type = ContentType.objects.get_for_model(test_post)
        comment = Comment(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content=""
        )
        
        with pytest.raises(ValidationError) as exc_info:
            comment.full_clean()
        
        assert 'content' in exc_info.value.message_dict
    
    def test_very_long_content(self, user, test_post):
        """Test handling of very long content."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        # Create content longer than typical max length
        long_content = "x" * 10000
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content=long_content
        )
        
        assert len(comment.content) == 10000
        assert comment.content == long_content
    
    def test_whitespace_only_content(self, user, test_post):
        """Test that whitespace-only content is handled."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        # Whitespace-only content
        comment = Comment(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content="   \n\t   "
        )
        
        # Should be saved
        comment.save()
        assert comment.pk is not None
    
    def test_invalid_content_type(self, user):
        """Test creating comment with invalid content type."""
        from django.contrib.contenttypes.models import ContentType as CT
        
        with pytest.raises((ValidationError, IntegrityError, CT.DoesNotExist)):
            Comment.objects.create(
                content_type_id=99999,  # Non-existent content type
                object_id="1",
                user=user,
                content="Test content"
            )


# ============================================================================
# COMMENT MODEL TESTS - EDGE CASES
# ============================================================================

@pytest.mark.models
@pytest.mark.unit
class TestCommentEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_special_characters_in_content(self, user, test_post):
        """Test comment with special characters."""
        content_type = ContentType.objects.get_for_model(test_post)
        special_content = "<script>alert('XSS')</script> & © ™ € £ ¥"
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content=special_content
        )
        
        # Content should be stored as-is (sanitization happens at display/serialization)
        assert comment.content == special_content
        assert "<script>" in comment.content
    
    def test_unicode_content(self, user, test_post):
        """Test comment with Unicode characters."""
        content_type = ContentType.objects.get_for_model(test_post)
        unicode_content = "Hello 世界 مرحبا こんにちは 안녕하세요 😀 🎉"
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content=unicode_content
        )
        
        assert comment.content == unicode_content
        assert "世界" in comment.content
        assert "😀" in comment.content
    
    def test_sql_injection_in_content(self, user, test_post):
        """Test that SQL injection attempts are safely stored."""
        content_type = ContentType.objects.get_for_model(test_post)
        sql_injection = "'; DROP TABLE comments; --"
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content=sql_injection
        )
        
        # Should be stored safely without executing
        assert comment.content == sql_injection
        assert Comment.objects.filter(pk=comment.pk).exists()
    
    def test_multiline_content(self, user, test_post):
        """Test comment with multiple lines."""
        content_type = ContentType.objects.get_for_model(test_post)
        multiline_content = """This is line 1
This is line 2
This is line 3

This is after blank line"""
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content=multiline_content
        )
        
        assert "\n" in comment.content
        assert comment.content.count("\n") >= 3
    
    def test_comment_with_null_user(self, test_post):
        """Test creating anonymous comment (null user)."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=None,
            user_name="Anonymous User",
            user_email="anon@example.com",
            content="Anonymous comment"
        )
        
        assert comment.user is None
        assert comment.user_name == "Anonymous User"
        assert comment.user_email == "anon@example.com"
        assert comment.get_user_name() == "Anonymous User"
    
    def test_comment_with_long_user_fields(self, test_post):
        """Test comment with very long anonymous user fields."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=None,
            user_name="A" * 100,  # Max length test
            user_email="test@example.com",
            content="Test"
        )
        
        assert len(comment.user_name) == 100
    
    def test_comment_on_deleted_user(self, user, test_post):
        """Test comment behavior when user is deleted."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            user_name=user.username,
            user_email=user.email,
            content="Test comment"
        )
        
        comment_id = comment.id
        
        # Delete user
        user.delete()
        
        # Comment should still exist with user set to None
        comment.refresh_from_db()
        assert comment.user is None
        assert comment.user_name  # Should retain the name
        assert comment.user_email  # Should retain the email


# ============================================================================
# COMMENT MODEL TESTS - THREADING
# ============================================================================

@pytest.mark.models
@pytest.mark.unit
class TestCommentThreading:
    """Test comment threading and hierarchical structures."""
    
    def test_root_comment_threading_fields(self, user, test_post):
        """Test threading fields for root comment."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content="Root comment"
        )
        
        assert comment.parent is None
        assert comment.level == 0
        assert comment.path == str(comment.id)
        assert comment.thread_id == str(comment.id)
    
    def test_child_comment_threading_fields(self, user, test_post):
        """Test threading fields for child comment."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        # Create parent
        parent = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content="Parent comment"
        )
        
        # Create child
        child = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            parent=parent,
            content="Child comment"
        )
        
        assert child.parent == parent
        assert child.level == 1
        assert child.path == f"{parent.path}/{child.id}"
        assert child.thread_id == parent.thread_id
    
    def test_grandchild_comment_threading(self, user, test_post):
        """Test threading with three levels."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        # Create hierarchy
        root = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content="Root"
        )
        
        child = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            parent=root,
            content="Child"
        )
        
        grandchild = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            parent=child,
            content="Grandchild"
        )
        
        assert grandchild.level == 2
        assert grandchild.path == f"{root.path}/{child.id}/{grandchild.id}"
        assert grandchild.thread_id == root.thread_id
        assert root.thread_id == child.thread_id == grandchild.thread_id
    
    def test_deep_threading(self, user, test_post):
        """Test very deep threading (10 levels)."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        parent = None
        comments = []
        
        for level in range(10):
            comment = Comment.objects.create(
                content_type=content_type,
                object_id=str(test_post.id),
                user=user,
                parent=parent,
                content=f"Level {level}"
            )
            comments.append(comment)
            parent = comment
        
        # Check last comment
        last_comment = comments[-1]
        assert last_comment.level == 9
        assert last_comment.thread_id == comments[0].thread_id
        
        # Check path contains all ancestor IDs
        path_parts = last_comment.path.split('/')
        assert len(path_parts) == 10
    
    def test_multiple_children_same_parent(self, user, test_post):
        """Test multiple children for same parent."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        parent = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content="Parent"
        )
        
        children = []
        for i in range(5):
            child = Comment.objects.create(
                content_type=content_type,
                object_id=str(test_post.id),
                user=user,
                parent=parent,
                content=f"Child {i}"
            )
            children.append(child)
        
        # All children should have same parent and thread_id
        for child in children:
            assert child.parent == parent
            assert child.thread_id == parent.thread_id
            assert child.level == 1
        
        # All children should have different IDs
        child_ids = [c.id for c in children]
        assert len(child_ids) == len(set(child_ids))
    
    def test_get_children_method(self, comment_thread):
        """Test getting children of a comment."""
        parent = comment_thread['parent']
        children = comment_thread['children']
        
        # Get children using query
        db_children = Comment.objects.filter(parent=parent)
        
        assert db_children.count() == len(children)
        assert set(db_children) == set(children)
    
    def test_get_descendants(self, comment_thread):
        """Test getting all descendants of a comment."""
        parent = comment_thread['parent']
        
        # Get all comments in the thread
        descendants = Comment.objects.filter(
            thread_id=parent.thread_id
        ).exclude(id=parent.id)
        
        # Should include children and grandchildren
        assert descendants.count() >= len(comment_thread['children'])


# ============================================================================
# COMMENT MODEL TESTS - STATUS FIELDS
# ============================================================================

@pytest.mark.models
@pytest.mark.unit
class TestCommentStatus:
    """Test comment status fields and visibility."""
    
    def test_default_is_public_true(self, user, test_post):
        """Test that comments are public by default."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content="Test"
        )
        
        assert comment.is_public is True
    
    def test_default_is_removed_false(self, user, test_post):
        """Test that comments are not removed by default."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content="Test"
        )
        
        assert comment.is_removed is False
    
    def test_create_private_comment(self, user, test_post):
        """Test creating a private (non-public) comment."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content="Private comment",
            is_public=False
        )
        
        assert comment.is_public is False
        assert comment.is_removed is False
    
    def test_create_removed_comment(self, user, test_post):
        """Test creating a removed comment."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content="Removed comment",
            is_removed=True
        )
        
        assert comment.is_removed is True
    
    def test_toggle_public_status(self, comment):
        """Test toggling public status."""
        original_status = comment.is_public
        
        comment.is_public = not original_status
        comment.save()
        
        comment.refresh_from_db()
        assert comment.is_public != original_status
    
    def test_toggle_removed_status(self, comment):
        """Test toggling removed status."""
        assert comment.is_removed is False
        
        comment.is_removed = True
        comment.save()
        
        comment.refresh_from_db()
        assert comment.is_removed is True
        
        comment.is_removed = False
        comment.save()
        
        comment.refresh_from_db()
        assert comment.is_removed is False


# ============================================================================
# COMMENT MODEL TESTS - STRING REPRESENTATION
# ============================================================================

@pytest.mark.models
@pytest.mark.unit
class TestCommentStringMethods:
    """Test comment string representation methods."""
    
    def test_comment_str_with_user(self, comment):
        """Test string representation for comment with user."""
        str_repr = str(comment)
        
        assert comment.user.username in str_repr or comment.user_name in str_repr
        assert str_repr  # Should not be empty
    
    def test_comment_str_anonymous(self, anonymous_comment):
        """Test string representation for anonymous comment."""
        str_repr = str(anonymous_comment)
        
        assert str_repr
        assert anonymous_comment.user_name in str_repr
    
    def test_get_user_name_authenticated(self, comment):
        """Test get_user_name for authenticated user."""
        user_name = comment.get_user_name()
        
        assert user_name == comment.user.username
    
    def test_get_user_name_anonymous(self, anonymous_comment):
        """Test get_user_name for anonymous comment."""
        user_name = anonymous_comment.get_user_name()
        
        assert user_name == anonymous_comment.user_name


# ============================================================================
# COMMENT MODEL TESTS - MANAGER METHODS
# ============================================================================

@pytest.mark.models
@pytest.mark.unit
class TestCommentManager:
    """Test Comment manager methods."""
    
    def test_all_returns_all_comments(self, comments):
        """Test that all() returns all comments."""
        all_comments = Comment.objects.all()
        
        assert all_comments.count() >= len(comments)
        for comment in comments:
            assert comment in all_comments
    
    def test_filter_by_content_type(self, test_post, test_post_with_uuid):
        """Test filtering comments by content type."""
        ct1 = ContentType.objects.get_for_model(test_post)
        ct2 = ContentType.objects.get_for_model(test_post_with_uuid)
        
        # Create comments for both types
        CommentFactory(content_type=ct1, object_id=test_post.id)
        CommentFactory(content_type=ct2, object_id=str(test_post_with_uuid.id))
        
        comments_ct1 = Comment.objects.filter(content_type=ct1)
        comments_ct2 = Comment.objects.filter(content_type=ct2)
        
        assert comments_ct1.count() >= 1
        assert comments_ct2.count() >= 1
    
    def test_filter_by_object_id(self, test_posts):
        """Test filtering comments by object ID."""
        post1 = test_posts[0]
        post2 = test_posts[1]
        
        ct = ContentType.objects.get_for_model(post1)
        
        # Create comments
        CommentFactory(content_type=ct, object_id=post1.id)
        CommentFactory(content_type=ct, object_id=post2.id)
        
        post1_comments = Comment.objects.filter(
            content_type=ct,
            object_id=str(post1.id)
        )
        
        assert post1_comments.count() >= 1
        assert all(c.object_id == str(post1.id) for c in post1_comments)
    
    def test_filter_public_comments(self, mixed_status_comments):
        """Test filtering only public comments."""
        public_comments = Comment.objects.filter(is_public=True)
        
        assert mixed_status_comments['public'] in public_comments
        assert mixed_status_comments['private'] not in public_comments
    
    def test_filter_non_removed_comments(self, mixed_status_comments):
        """Test filtering non-removed comments."""
        non_removed = Comment.objects.filter(is_removed=False)
        
        assert mixed_status_comments['public'] in non_removed
        assert mixed_status_comments['removed'] not in non_removed
    
    def test_order_by_submit_date(self, comments):
        """Test ordering comments by submit date."""
        ordered = Comment.objects.filter(
            id__in=[c.id for c in comments]
        ).order_by('submit_date')
        
        dates = [c.submit_date for c in ordered]
        assert dates == sorted(dates)


# ============================================================================
# COMMENT FLAG MODEL TESTS
# ============================================================================

@pytest.mark.models
@pytest.mark.unit
class TestCommentFlagCreation:
    """Test CommentFlag model creation."""
    
    def test_create_flag(self, comment, user):
        """Test creating a flag on a comment."""
        flag = CommentFlag.objects.create(
            comment=comment,
            user=user,
            flag='spam',
            reason='This is spam content'
        )
        
        assert flag.pk is not None
        assert flag.comment == comment
        assert flag.user == user
        assert flag.flag == 'spam'
        assert flag.reason == 'This is spam content'
    
    def test_flag_types(self, comment):
        """Test different flag types."""
        flag_types = ['spam', 'inappropriate', 'offensive', 'other']
        
        flags = []
        for flag_type in flag_types:
            user_for_flag = UserFactory()
            flag = CommentFlag.objects.create(
                comment=comment,
                user=user_for_flag,
                flag=flag_type,
                reason=f'Reason for {flag_type}'
            )
            flags.append(flag)
        
        assert len(flags) == 4
        assert all(f.flag in flag_types for f in flags)
    
    def test_multiple_flags_same_comment(self, comment):
        """Test multiple users flagging same comment."""
        users = [UserFactory() for _ in range(5)]
        
        flags = []
        for user in users:
            flag = CommentFlag.objects.create(
                comment=comment,
                user=user,
                flag='spam',
                reason='Spam'
            )
            flags.append(flag)
        
        assert CommentFlag.objects.filter(comment=comment).count() == 5
    
    def test_flag_with_empty_reason(self, comment, user):
        """Test creating flag with empty reason."""
        flag = CommentFlag.objects.create(
            comment=comment,
            user=user,
            flag='spam',
            reason=''
        )
        
        assert flag.pk is not None
        assert flag.reason == ''
    
    def test_flag_auto_timestamp(self, comment, user):
        """Test that flag timestamp is set automatically."""
        flag = CommentFlag.objects.create(
            comment=comment,
            user=user,
            flag='spam',
            reason='Test'
        )
        
        assert flag.flagged_at is not None
        assert flag.flagged_at <= timezone.now()


@pytest.mark.models
@pytest.mark.unit
class TestCommentFlagValidation:
    """Test CommentFlag validation and constraints."""
    
    def test_flag_requires_comment(self, user):
        """Test that comment is required."""
        with pytest.raises((ValidationError, IntegrityError)):
            CommentFlag.objects.create(
                user=user,
                flag='spam',
                reason='Test'
            )
    
    def test_flag_requires_user(self, comment):
        """Test that user is required."""
        with pytest.raises((ValidationError, IntegrityError)):
            CommentFlag.objects.create(
                comment=comment,
                flag='spam',
                reason='Test'
            )
    
    def test_flag_requires_flag_type(self, comment, user):
        """Test that flag type is required."""
        with pytest.raises((ValidationError, IntegrityError)):
            flag = CommentFlag(
                comment=comment,
                user=user,
                reason='Test'
            )
            flag.save()


# ============================================================================
# REAL-WORLD SCENARIO TESTS
# ============================================================================

@pytest.mark.models
@pytest.mark.integration
class TestRealWorldScenarios:
    """Test real-world usage scenarios."""
    
    def test_blog_post_comments(self, users, test_post):
        """Simulate typical blog post comments."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        # Multiple users comment
        comments = []
        for user in users[:3]:
            comment = Comment.objects.create(
                content_type=content_type,
                object_id=str(test_post.id),
                user=user,
                content=f"Great post! - {user.username}"
            )
            comments.append(comment)
        
        # Some replies
        reply = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=users[3],
            parent=comments[0],
            content="I agree!"
        )
        
        # Verify structure
        assert Comment.objects.filter(
            content_type=content_type,
            object_id=str(test_post.id)
        ).count() == 4
        assert reply.parent == comments[0]
    
    def test_moderation_workflow(self, user, test_post):
        """Simulate comment moderation workflow."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        # User posts comment
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=user,
            content="Test comment",
            is_public=False
        )
        
        assert comment.is_public is False
        
        # Multiple users flag it
        flaggers = [UserFactory() for _ in range(3)]
        for flagger in flaggers:
            CommentFlag.objects.create(
                comment=comment,
                user=flagger,
                flag='inappropriate',
                reason='Offensive content'
            )
        
        assert CommentFlag.objects.filter(comment=comment).count() == 3
        
        # Moderator removes it
        comment.is_removed = True
        comment.save()
        
        assert comment.is_removed is True
    
    def test_nested_discussion(self, users, test_post):
        """Simulate a nested discussion thread."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        # Start discussion
        root = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=users[0],
            content="What do you think?"
        )
        
        # User 2 replies
        reply1 = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=users[1],
            parent=root,
            content="Interesting point"
        )
        
        # User 3 replies to User 2
        reply2 = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=users[2],
            parent=reply1,
            content="I disagree"
        )
        
        # User 1 replies to User 3
        reply3 = Comment.objects.create(
            content_type=content_type,
            object_id=str(test_post.id),
            user=users[0],
            parent=reply2,
            content="Here's why..."
        )
        
        # Verify thread structure
        assert reply1.level == 1
        assert reply2.level == 2
        assert reply3.level == 3
        assert all(c.thread_id == root.thread_id for c in [reply1, reply2, reply3])