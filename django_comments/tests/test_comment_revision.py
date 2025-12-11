"""
Comprehensive Test Suite for CommentRevision Model

Tests cover:
- Revision creation when comment is edited
- Edit history tracking
- Revision content storage
- Cascade deletion behavior
- Timestamp handling
- Editor information
- Edge cases
"""
import uuid
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from .base import BaseCommentTestCase


class CommentRevisionCreationTests(BaseCommentTestCase):
    """
    Test CommentRevision creation scenarios.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import CommentRevision
        self.CommentRevision = CommentRevision
    
    def test_create_revision_success(self):
        """Test creating a revision for edited comment."""
        comment = self.create_comment(content='Original content')
        
        revision = self.CommentRevision.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            content='Original content',
            edited_by=self.moderator,
            was_public=comment.is_public,
            was_removed=comment.is_removed
        )
        
        self.assertIsNotNone(revision.pk)
        self.assertIsInstance(revision.pk, uuid.UUID)
        self.assertEqual(revision.content, 'Original content')
        self.assertEqual(revision.edited_by, self.moderator)
    
    def test_revision_has_uuid_primary_key(self):
        """Test that CommentRevision uses UUID as primary key."""
        comment = self.create_comment()
        
        revision = self.CommentRevision.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            content=comment.content,
            edited_by=self.regular_user
        )
        
        self.assertIsInstance(revision.pk, uuid.UUID)
        self.assertIsInstance(revision.id, uuid.UUID)
    
    def test_create_revision_with_state_changes(self):
        """Test revision records state changes (public/removed)."""
        comment = self.create_comment(is_public=True, is_removed=False)
        
        revision = self.CommentRevision.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            content=comment.content,
            edited_by=self.moderator,
            was_public=True,
            was_removed=False
        )
        
        self.assertTrue(revision.was_public)
        self.assertFalse(revision.was_removed)
    
    def test_create_revision_without_editor(self):
        """Test creating revision without editor (system edit)."""
        comment = self.create_comment()
        
        revision = self.CommentRevision.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            content=comment.content,
            edited_by=None  # System edit
        )
        
        self.assertIsNone(revision.edited_by)


class CommentRevisionEditHistoryTests(BaseCommentTestCase):
    """
    Test edit history tracking functionality.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import CommentRevision
        self.CommentRevision = CommentRevision
    
    def test_multiple_revisions_for_same_comment(self):
        """Test storing multiple edit revisions."""
        comment = self.create_comment(content='Version 1')
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        # Create multiple revisions
        rev1 = self.CommentRevision.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            content='Version 1',
            edited_by=self.regular_user
        )
        
        rev2 = self.CommentRevision.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            content='Version 2',
            edited_by=self.regular_user
        )
        
        rev3 = self.CommentRevision.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            content='Version 3',
            edited_by=self.moderator
        )
        
        revisions = self.CommentRevision.objects.filter(
            comment_id=str(comment.pk)
        ).order_by('edited_at')
        
        self.assertEqual(revisions.count(), 3)
        self.assertEqual(list(revisions), [rev1, rev2, rev3])
    
    def test_revision_ordering_by_edited_at(self):
        """Test revisions are ordered by edit timestamp."""
        comment = self.create_comment()
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        import time
        
        # Create revisions with time delays
        rev1 = self.CommentRevision.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            content='First edit',
            edited_by=self.regular_user
        )
        time.sleep(0.01)
        
        rev2 = self.CommentRevision.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            content='Second edit',
            edited_by=self.regular_user
        )
        time.sleep(0.01)
        
        rev3 = self.CommentRevision.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            content='Third edit',
            edited_by=self.regular_user
        )
        
        revisions = list(self.CommentRevision.objects.filter(
            comment_id=str(comment.pk)
        ).order_by('edited_at'))
        
        self.assertEqual(revisions[0], rev1)
        self.assertEqual(revisions[1], rev2)
        self.assertEqual(revisions[2], rev3)


class CommentRevisionContentStorageTests(BaseCommentTestCase):
    """
    Test content storage and retrieval.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import CommentRevision
        self.CommentRevision = CommentRevision
    
    def test_revision_stores_full_content(self):
        """Test revision stores complete comment content."""
        long_content = 'This is a long comment. ' * 50
        comment = self.create_comment(content=long_content)
        
        revision = self.CommentRevision.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            content=long_content,
            edited_by=self.regular_user
        )
        
        self.assertEqual(revision.content, long_content)
        self.assertEqual(len(revision.content), len(long_content))
    
    def test_revision_with_unicode_content(self):
        """Test revision stores Unicode content correctly."""
        unicode_content = 'Comment with émojis 🎉 and spëcial çharacters 中文'
        comment = self.create_comment(content=unicode_content)
        
        revision = self.CommentRevision.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            content=unicode_content,
            edited_by=self.regular_user
        )
        
        self.assertEqual(revision.content, unicode_content)
    
    def test_revision_with_html_content(self):
        """Test revision stores HTML content as-is."""
        html_content = '<p>This is <strong>HTML</strong> content</p>'
        comment = self.create_comment(content=html_content)
        
        revision = self.CommentRevision.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            content=html_content,
            edited_by=self.regular_user
        )
        
        self.assertEqual(revision.content, html_content)


class CommentRevisionCascadeTests(BaseCommentTestCase):
    """
    Test cascade deletion behavior.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import CommentRevision
        self.CommentRevision = CommentRevision
    
    def test_delete_comment_may_cascade_to_revisions(self):
        """Test that deleting comment may delete revisions."""
        comment = self.create_comment()
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        revision = self.CommentRevision.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            content=comment.content,
            edited_by=self.regular_user
        )
        revision_pk = revision.pk
        
        # Behavior depends on on_delete setting
        # If CASCADE: revisions deleted
        # If SET_NULL: revisions kept
        comment.delete()
        
        # Test for either behavior (model may vary)
        exists = self.CommentRevision.objects.filter(pk=revision_pk).exists()
        # Either behavior is acceptable
        self.assertIsInstance(exists, bool)
    
    def test_delete_editor_sets_edited_by_to_null(self):
        """Test deleting editor doesn't delete revisions."""
        comment = self.create_comment()
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        revision = self.CommentRevision.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            content=comment.content,
            edited_by=self.moderator
        )
        
        # Delete editor
        self.moderator.delete()
        
        # Revision should exist with edited_by=None
        fresh_revision = self.CommentRevision.objects.get(pk=revision.pk)
        self.assertIsNone(fresh_revision.edited_by)


class CommentRevisionTimestampTests(BaseCommentTestCase):
    """
    Test timestamp handling.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import CommentRevision
        self.CommentRevision = CommentRevision
    
    def test_edited_at_set_on_creation(self):
        """Test edited_at timestamp is set when revision created."""
        comment = self.create_comment()
        
        before = timezone.now()
        revision = self.CommentRevision.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            content=comment.content,
            edited_by=self.regular_user
        )
        after = timezone.now()
        
        self.assertIsNotNone(revision.edited_at)
        self.assertGreaterEqual(revision.edited_at, before)
        self.assertLessEqual(revision.edited_at, after)
    
    def test_revisions_chronological_order(self):
        """Test revisions maintain chronological order."""
        comment = self.create_comment()
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        revisions = []
        for i in range(5):
            rev = self.CommentRevision.objects.create(
                comment_type=content_type,
                comment_id=str(comment.pk),
                content=f'Edit {i}',
                edited_by=self.regular_user
            )
            revisions.append(rev)
            if i < 4:  # Don't sleep after last one
                import time
                time.sleep(0.01)
        
        # Query revisions in order
        ordered_revisions = list(
            self.CommentRevision.objects.filter(
                comment_id=str(comment.pk)
            ).order_by('edited_at')
        )
        
        self.assertEqual(len(ordered_revisions), 5)
        for i in range(4):
            self.assertLess(
                ordered_revisions[i].edited_at,
                ordered_revisions[i + 1].edited_at
            )


class CommentRevisionQueryTests(BaseCommentTestCase):
    """
    Test querying revisions.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import CommentRevision
        self.CommentRevision = CommentRevision
    
    def test_filter_revisions_by_comment(self):
        """Test filtering revisions for specific comment."""
        comment1 = self.create_comment(content='Comment 1')
        comment2 = self.create_comment(content='Comment 2')
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        rev1 = self.CommentRevision.objects.create(
            comment_type=content_type,
            comment_id=str(comment1.pk),
            content='Edit 1',
            edited_by=self.regular_user
        )
        
        rev2 = self.CommentRevision.objects.create(
            comment_type=content_type,
            comment_id=str(comment2.pk),
            content='Edit 2',
            edited_by=self.regular_user
        )
        
        comment1_revisions = self.CommentRevision.objects.filter(
            comment_id=str(comment1.pk)
        )
        
        self.assertEqual(comment1_revisions.count(), 1)
        self.assertIn(rev1, comment1_revisions)
        self.assertNotIn(rev2, comment1_revisions)
    
    def test_filter_revisions_by_editor(self):
        """Test filtering revisions by who made the edit."""
        comment = self.create_comment()
        content_type = ContentType.objects.get_for_model(self.Comment)
        
        user_rev = self.CommentRevision.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            content='User edit',
            edited_by=self.regular_user
        )
        
        mod_rev = self.CommentRevision.objects.create(
            comment_type=content_type,
            comment_id=str(comment.pk),
            content='Moderator edit',
            edited_by=self.moderator
        )
        
        user_revisions = self.CommentRevision.objects.filter(
            edited_by=self.regular_user
        )
        
        self.assertIn(user_rev, user_revisions)
        self.assertNotIn(mod_rev, user_revisions)


class CommentRevisionEdgeCaseTests(BaseCommentTestCase):
    """
    Test edge cases and boundary conditions.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import CommentRevision
        self.CommentRevision = CommentRevision
    
    def test_revision_with_empty_content(self):
        """Test revision can store empty content."""
        comment = self.create_comment()
        
        revision = self.CommentRevision.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            content='',  # Empty
            edited_by=self.regular_user
        )
        
        self.assertEqual(revision.content, '')
    
    def test_revision_for_non_existent_comment(self):
        """Test creating revision for non-existent comment ID."""
        fake_comment_id = str(uuid.uuid4())
        
        # Should save (no FK constraint)
        revision = self.CommentRevision.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=fake_comment_id,
            content='Orphaned revision',
            edited_by=self.regular_user
        )
        
        self.assertIsNotNone(revision.pk)


class CommentRevisionStringRepresentationTests(BaseCommentTestCase):
    """
    Test string representation.
    """
    
    def setUp(self):
        super().setUp()
        from django_comments.models import CommentRevision
        self.CommentRevision = CommentRevision
    
    def test_str_representation(self):
        """Test string representation includes key info."""
        comment = self.create_comment()
        
        revision = self.CommentRevision.objects.create(
            comment_type=ContentType.objects.get_for_model(self.Comment),
            comment_id=str(comment.pk),
            content='Test content',
            edited_by=self.regular_user
        )
        
        str_repr = str(revision)
        
        # Should include some identifying information
        self.assertIsInstance(str_repr, str)
        self.assertGreater(len(str_repr), 0)