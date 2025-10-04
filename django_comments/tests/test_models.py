"""
Tests for the Comment and CommentFlag models.
"""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.db import IntegrityError, transaction
from ..models import Comment, CommentFlag
from .factories import UserFactory


@pytest.mark.django_db
class TestCommentModel:
    """
    Tests for the Comment model.
    """
    
    def test_create_comment(self, user, test_post):
        """Test creating a comment."""
        content_type = ContentType.objects.get_for_model(test_post)
        
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=test_post.id,
            user=user,
            content="This is a test comment."
        )
        
        assert comment.pk is not None
        assert comment.content == "This is a test comment."
        assert comment.user == user
        assert comment.content_object == test_post
        assert comment.is_public is True
        assert comment.is_removed is False
        
    def test_comment_str(self, comment):
        """Test string representation of a comment."""
        expected_str = f"Comment by {comment.get_user_name()} on {comment.content_object}"
        assert str(comment) == expected_str
        
    def test_get_user_name(self, comment, user):
        """Test get_user_name method."""
        # With user
        assert comment.get_user_name() == user.get_username()
        
        # Without user, with user_name
        comment.user = None
        comment.user_name = "Test User"
        assert comment.get_user_name() == "Test User"
        
        # Without user, without user_name
        comment.user_name = ""
        assert comment.get_user_name() == "Anonymous"
        
    def test_comment_path_generation(self, comment_thread):
        """Test path generation for threaded comments."""
        parent = comment_thread['parent']
        child = comment_thread['children'][0]
        grandchild = comment_thread['grandchild']
        
        # Check paths
        assert parent.path == str(parent.pk)
        assert child.path == f"{parent.pk}/{child.pk}"
        assert grandchild.path == f"{parent.pk}/{child.pk}/{grandchild.pk}"
        
        # Check thread_id
        assert parent.thread_id == str(parent.pk)
        assert child.thread_id == parent.thread_id
        assert grandchild.thread_id == parent.thread_id
        
    def test_depth_property(self, comment_thread):
        """Test depth property."""
        parent = comment_thread['parent']
        child = comment_thread['children'][0]
        grandchild = comment_thread['grandchild']
        
        assert parent.depth == 0
        assert child.depth == 1
        assert grandchild.depth == 2
        
    def test_get_descendants(self, comment_thread):
        """Test get_descendants method."""
        parent = comment_thread['parent']
        children = comment_thread['children']
        grandchild = comment_thread['grandchild']
        
        descendants = parent.get_descendants()
        assert descendants.count() == len(children) + 1  # All children + grandchild
        
        # Check if all children are in descendants
        for child in children:
            assert child in descendants
            
        assert grandchild in descendants
        
    def test_get_ancestors(self, comment_thread):
        """Test get_ancestors method."""
        parent = comment_thread['parent']
        child = comment_thread['children'][0]
        grandchild = comment_thread['grandchild']
        
        # Parent has no ancestors
        assert parent.get_ancestors().count() == 0
        
        # Child has parent as ancestor
        assert child.get_ancestors().count() == 1
        assert parent in child.get_ancestors()
        
        # Grandchild has parent and child as ancestors
        assert grandchild.get_ancestors().count() == 2
        assert parent in grandchild.get_ancestors()
        assert child in grandchild.get_ancestors()
        
    def test_is_edited_property(self, comment):
        """Test is_edited property."""
        assert comment.is_edited is False

        # Simulate editing with timestamp > 30 seconds after created_at
        new_updated_at = comment.created_at + timezone.timedelta(minutes=5)
        Comment.objects.filter(pk=comment.pk).update(
            content="Updated content",
            updated_at=new_updated_at
        )

        comment.refresh_from_db()
        assert comment.is_edited is True
        

@pytest.mark.django_db
class TestCommentFlagModel:
    """
    Tests for the CommentFlag model.
    """
    
    def test_create_comment_flag(self, comment, user):
        """Test creating a comment flag."""
        flag = CommentFlag.objects.create(
            comment=comment,
            user=user,
            flag='spam',
            reason='This looks like spam.'
        )
        
        assert flag.pk is not None
        assert flag.comment == comment
        assert flag.user == user
        assert flag.flag == 'spam'
        assert flag.reason == 'This looks like spam.'
        
    def test_comment_flag_str(self, comment, user):
        """Test string representation of a comment flag."""
        flag = CommentFlag.objects.create(
            comment=comment,
            user=user,
            flag='offensive',
            reason='This is offensive.'
        )
        
        expected_str = f"{user.get_username()} flagged comment {comment.pk} as Offensive"
        assert str(flag) == expected_str
        
    def test_flag_unique_constraint(self, comment, user):
        """Test unique constraint for comment flags."""
        # Create the first flag
        CommentFlag.objects.create(
            comment=comment,
            user=user,
            flag='spam'
        )

        # Try to create another flag with the same user, comment, and flag
        with pytest.raises(IntegrityError):
            with transaction.atomic():  # Isolate the failure
                CommentFlag.objects.create(
                    comment=comment,
                    user=user,
                    flag='spam'
                )

        # Should work with a different flag type
        flag2 = CommentFlag.objects.create(
            comment=comment,
            user=user,
            flag='offensive'
        )
        assert flag2.pk is not None

        # Should work with a different user
        user2 = UserFactory()
        flag3 = CommentFlag.objects.create(
            comment=comment,
            user=user2,
            flag='spam'
        )
        assert flag3.pk is not None