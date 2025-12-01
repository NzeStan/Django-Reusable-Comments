"""
Tests for the django_comments managers and querysets.
CRITICAL: These tests cover core query functionality.
"""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count

from ..models import Comment
from .factories import UserFactory, CommentFactory, CommentFlagFactory
from .models import TestPost


@pytest.mark.django_db
class TestCommentQuerySet:
    """Tests for CommentQuerySet methods."""
    
    def test_for_model_with_instance(self, test_post, comment):
        """Test for_model with model instance."""
        comments = Comment.objects.for_model(test_post)
        
        assert comments.count() == 1
        assert comment in comments
    
    def test_for_model_with_class(self, test_post, comment):
        """Test for_model with model class."""
        comments = Comment.objects.for_model(TestPost)
        
        assert comments.count() >= 1
        assert comment in comments
    
    def test_public(self, user, test_post):
        """Test public queryset returns only public comments."""
        # Create public comment
        public_comment = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            is_public=True,
            is_removed=False
        )
        
        # Create non-public comment
        non_public = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            is_public=False
        )
        
        # Create removed comment
        removed = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            is_public=True,
            is_removed=True
        )
        
        public_comments = Comment.objects.public()
        
        assert public_comment in public_comments
        assert non_public not in public_comments
        assert removed not in public_comments
    
    def test_removed(self, user, test_post):
        """Test removed queryset returns only removed comments."""
        # Create removed comment
        removed = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            is_removed=True
        )
        
        # Create non-removed comment
        not_removed = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            is_removed=False
        )
        
        removed_comments = Comment.objects.removed()
        
        assert removed in removed_comments
        assert not_removed not in removed_comments
    
    def test_not_public(self, user, test_post):
        """Test not_public returns non-public, non-removed comments."""
        # Create non-public comment
        non_public = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            is_public=False,
            is_removed=False
        )
        
        # Create public comment
        public = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            is_public=True
        )
        
        # Create removed comment
        removed = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            is_public=False,
            is_removed=True
        )
        
        moderation_queue = Comment.objects.not_public()
        
        assert non_public in moderation_queue
        assert public not in moderation_queue
        assert removed not in moderation_queue
    
    def test_flagged(self, user, test_post):
        """Test flagged returns comments with flags."""
        # Create comment with flag
        flagged_comment = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user
        )
        CommentFlagFactory(comment=flagged_comment, user=UserFactory())
        
        # Create comment without flag
        unflagged = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user
        )
        
        flagged_comments = Comment.objects.flagged()
        
        assert flagged_comment in flagged_comments
        assert unflagged not in flagged_comments
    
    def test_root_nodes(self, comment_thread):
        """Test root_nodes returns only comments without parent."""
        parent = comment_thread['parent']
        children = comment_thread['children']
        
        root_comments = Comment.objects.root_nodes()
        
        assert parent in root_comments
        for child in children:
            assert child not in root_comments
    
    def test_by_user(self, user, test_post):
        """Test by_user returns comments by specific user."""
        user2 = UserFactory()
        
        # Comments by user
        user_comment = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user
        )
        
        # Comments by user2
        other_comment = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user2
        )
        
        user_comments = Comment.objects.by_user(user)
        
        assert user_comment in user_comments
        assert other_comment not in user_comments
    
    def test_by_thread(self, comment_thread):
        """Test by_thread returns all comments in thread."""
        parent = comment_thread['parent']
        children = comment_thread['children']
        grandchild = comment_thread['grandchild']
        
        thread_comments = Comment.objects.by_thread(parent.thread_id)
        
        assert parent in thread_comments
        for child in children:
            assert child in thread_comments
        assert grandchild in thread_comments
    
    def test_search_by_content(self, user, test_post):
        """Test search by comment content."""
        # Create comment with specific content
        searchable = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            content="This contains unique-search-term for testing"
        )
        
        # Create comment without search term
        other = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            content="Regular comment"
        )
        
        results = Comment.objects.search("unique-search-term")
        
        assert searchable in results
        assert other not in results
    
    def test_search_by_username(self, test_post):
        """Test search by username."""
        user = UserFactory(username="uniqueuser123")
        
        # Comment by user with unique username
        searchable = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=user,
            content="Regular content"
        )
        
        # Comment by different user
        other_user = UserFactory(username="commonuser")
        other = CommentFactory(
            content_type=ContentType.objects.get_for_model(test_post),
            object_id=test_post.id,
            user=other_user,
            content="Regular content"
        )
        
        results = Comment.objects.search("uniqueuser123")
        
        assert searchable in results
        assert other not in results
    
    def test_create_with_flags(self, user, test_post):
        """Test creating comment with flags."""
        ct = ContentType.objects.get_for_model(test_post)
        flagger = UserFactory()
        
        comment = Comment.objects.create_with_flags(
            content_type=ct,
            object_id=test_post.id,
            user=user,
            content="Test content",
            flags=[
                {'user': flagger, 'flag': 'spam', 'reason': 'Test reason'}
            ]
        )
        
        assert comment.pk is not None
        assert comment.flags.count() == 1
        assert comment.flags.first().flag == 'spam'


@pytest.mark.django_db
class TestCommentManager:
    """Tests for CommentManager methods."""
    
    def test_get_by_content_object(self, comment, test_post):
        """Test getting comments by content object."""
        comments = Comment.objects.get_by_content_object(test_post)
        
        assert comments.count() >= 1
        assert comment in comments
    
    def test_get_by_model_and_id(self, comment, test_post):
        """Test getting comments by model and id."""
        comments = Comment.objects.get_by_model_and_id(TestPost, test_post.id)
        
        assert comments.count() >= 1
        assert comment in comments
    
    def test_create_for_object(self, user, test_post):
        """Test creating comment for object."""
        comment = Comment.objects.create_for_object(
            test_post,
            user=user,
            content="Test comment"
        )
        
        assert comment.pk is not None
        assert comment.content_object == test_post
        assert comment.content == "Test comment"
        assert comment.user == user


@pytest.mark.django_db
class TestOptimizedQuerysets:
    """Tests for optimized queryset methods (if optimizations applied)."""
    
    def test_with_user_and_content_type(self, comment):
        """Test with_user_and_content_type optimization."""
        # This should use select_related
        comments = Comment.objects.filter(pk=comment.pk).with_user_and_content_type()
        
        # Access related objects (should not cause extra queries)
        comment_obj = comments.first()
        assert comment_obj.user is not None
        assert comment_obj.content_type is not None
    
    def test_with_parent_info(self, comment_thread):
        """Test with_parent_info optimization."""
        child = comment_thread['children'][0]
        
        # This should use select_related for parent and parent__user
        comments = Comment.objects.filter(pk=child.pk).with_parent_info()
        
        # Access parent and parent's user (should not cause extra queries)
        comment_obj = comments.first()
        assert comment_obj.parent is not None
        assert comment_obj.parent.user is not None
    
    def test_with_flags(self, comment):
        """Test with_flags optimization."""
        # Add a flag
        CommentFlagFactory(comment=comment, user=UserFactory())
        
        # This should prefetch flags
        comments = Comment.objects.filter(pk=comment.pk).with_flags()
        
        # Access flags (should not cause extra queries)
        comment_obj = comments.first()
        assert comment_obj.flags.count() == 1
        # Should have annotation
        assert hasattr(comment_obj, 'flags_count_annotated')
    
    def test_with_children_count(self, comment_thread):
        """Test with_children_count optimization."""
        parent = comment_thread['parent']
        
        # This should annotate children count
        comments = Comment.objects.filter(pk=parent.pk).with_children_count()
        
        comment_obj = comments.first()
        assert hasattr(comment_obj, 'children_count_annotated')
        assert comment_obj.children_count_annotated > 0
    
    def test_optimized_for_list(self, comment):
        """Test optimized_for_list combines all optimizations."""
        # This should apply all optimizations
        comments = Comment.objects.filter(pk=comment.pk).optimized_for_list()
        
        comment_obj = comments.first()
        
        # Check all optimizations are applied
        assert comment_obj.user is not None  # select_related
        assert comment_obj.content_type is not None  # select_related
        assert hasattr(comment_obj, 'flags_count_annotated')  # annotation
        assert hasattr(comment_obj, 'children_count_annotated')  # annotation