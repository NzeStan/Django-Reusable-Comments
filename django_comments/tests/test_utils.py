"""
Tests for the django_comments utility functions.
"""
import pytest
from django.contrib.contenttypes.models import ContentType

from ..conf import comments_settings
from ..utils import (
    get_comment_model,
    get_commentable_models,
    get_commentable_content_types,
    get_model_from_content_type_string,
    get_object_from_content_type_and_id,
    is_comment_content_allowed,
    filter_profanity,
    check_comment_permissions
)
from .models import TestPost


@pytest.mark.django_db
class TestCommentUtils:
    """Tests for the comment utility functions."""

    def test_get_comment_model(self):
        """Test get_comment_model function."""
        Comment = get_comment_model()
        assert Comment.__name__ == 'Comment'
        
    def test_get_commentable_models(self):
        """Test get_commentable_models function."""
        models = get_commentable_models()
        assert TestPost in models
        
    def test_get_commentable_content_types(self):
        """Test get_commentable_content_types function."""
        content_types = get_commentable_content_types()
        test_post_ct = ContentType.objects.get_for_model(TestPost)
        assert test_post_ct in content_types
        
    

    def test_get_model_from_content_type_string(self):
        app_label  = TestPost._meta.app_label      # e.g. 'tests'
        model_name = TestPost._meta.model_name     # e.g. 'testpost'
        ct_string  = f"{app_label}.{model_name}"

        model = get_model_from_content_type_string(ct_string)
        assert model == TestPost

        # invalid string still returns None
        assert get_model_from_content_type_string('invalid.model') is None


    def test_get_object_from_content_type_and_id(self, test_post):
        app_label  = TestPost._meta.app_label
        model_name = TestPost._meta.model_name
        ct_string  = f"{app_label}.{model_name}"

        obj = get_object_from_content_type_and_id(ct_string, test_post.id)
        assert obj == test_post

        # non‑existent pk returns None
        assert get_object_from_content_type_and_id(ct_string, 999999) is None

        # totally invalid content type returns None
        assert get_object_from_content_type_and_id('invalid.model', test_post.id) is None


        
    def test_is_comment_content_allowed(self, monkeypatch):
        """Test is_comment_content_allowed function."""
        # Test basic validation
        assert is_comment_content_allowed("This is a valid comment.") is True
        assert is_comment_content_allowed("") is False
        
        # Test maximum length validation
        monkeypatch.setattr(comments_settings, 'MAX_COMMENT_LENGTH', 10)
        assert is_comment_content_allowed("Short") is True
        assert is_comment_content_allowed("This is a very long comment.") is False
        
        # Test spam detection
        monkeypatch.setattr(comments_settings, 'MAX_COMMENT_LENGTH', 100)
        monkeypatch.setattr(comments_settings, 'SPAM_DETECTION_ENABLED', True)
        monkeypatch.setattr(comments_settings, 'SPAM_WORDS', ['spam', 'viagra'])
        
        assert is_comment_content_allowed("This is a normal comment.") is True
        assert is_comment_content_allowed("This contains spam word.") is False
        assert is_comment_content_allowed("This contains VIAGRA word.") is False
        
        # Test profanity filtering
        monkeypatch.setattr(comments_settings, 'SPAM_DETECTION_ENABLED', False)
        monkeypatch.setattr(comments_settings, 'PROFANITY_FILTERING', True)
        monkeypatch.setattr(comments_settings, 'PROFANITY_LIST', ['badword', 'taboo'])
        
        # With 'censor' action, content should still be allowed
        monkeypatch.setattr(comments_settings, 'PROFANITY_ACTION', 'censor')
        assert is_comment_content_allowed("This contains badword.") is True
        
        # With 'hide' action, content should be disallowed
        monkeypatch.setattr(comments_settings, 'PROFANITY_ACTION', 'hide')
        assert is_comment_content_allowed("This contains badword.") is False
        
    def test_filter_profanity(self, monkeypatch):
        """Test filter_profanity function."""
        # When profanity filtering is disabled
        monkeypatch.setattr(comments_settings, 'PROFANITY_FILTERING', False)
        assert filter_profanity("This contains badword.") == "This contains badword."
        
        # When profanity filtering is enabled with 'censor' action
        monkeypatch.setattr(comments_settings, 'PROFANITY_FILTERING', True)
        monkeypatch.setattr(comments_settings, 'PROFANITY_LIST', ['badword', 'taboo'])
        monkeypatch.setattr(comments_settings, 'PROFANITY_ACTION', 'censor')
        
        # Check censoring
        assert filter_profanity("This contains badword.") == "This contains *******."
        assert filter_profanity("This contains BADWORD.") == "This contains *******."
        assert filter_profanity("This contains taboo word.") == "This contains ***** word."
        
        # When profanity filtering is enabled with non-censor action
        monkeypatch.setattr(comments_settings, 'PROFANITY_ACTION', 'hide')
        assert filter_profanity("This contains badword.") == "This contains badword."
        
    def test_check_comment_permissions(self, comment, user, staff_user):
        """Test check_comment_permissions function."""
        # Anonymous user permissions
        anonymous_user = type('AnonymousUser', (), {'is_anonymous': True, 'is_staff': False, 'is_superuser': False})()
        
        # View permissions
        assert check_comment_permissions(anonymous_user, comment, 'view') is True  # Public comment
        
        comment.is_public = False
        assert check_comment_permissions(anonymous_user, comment, 'view') is False  # Non-public comment
        
        # Add permissions
        assert check_comment_permissions(anonymous_user, comment, 'add') is True  # If ALLOW_ANONYMOUS is True
        
        # Authenticated user permissions
        assert check_comment_permissions(user, comment, 'view') is True  # Own comment
        
        # Edit/delete permissions
        assert check_comment_permissions(user, comment, 'change') is True  # Own comment
        assert check_comment_permissions(user, comment, 'delete') is True  # Own comment
        
        # Other user's comment
        other_comment = type('Comment', (), {'user': staff_user, 'is_public': True, 'is_removed': False})()
        assert check_comment_permissions(user, other_comment, 'change') is False
        assert check_comment_permissions(user, other_comment, 'delete') is False
        
        # Staff user permissions
        assert check_comment_permissions(staff_user, comment, 'change') is True
        assert check_comment_permissions(staff_user, comment, 'delete') is True
        assert check_comment_permissions(staff_user, comment, 'moderate') is True