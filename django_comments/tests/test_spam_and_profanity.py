# test_spam_and_profanity.py
"""
Tests for spam detection and profanity filtering features.
Place this file in: django_comments/tests/test_spam_and_profanity.py
"""
import pytest
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django_comments.models import Comment, CommentFlag
from django_comments.utils import (
    check_content_for_spam,
    check_content_for_profanity,
    filter_profanity,
    is_comment_content_allowed,
    process_comment_content,
    apply_automatic_flags,
)

User = get_user_model()


class SpamDetectionTestCase(TestCase):
    """Test spam detection functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'SPAM_DETECTION_ENABLED': True,
        'SPAM_WORDS': ['viagra', 'casino', 'winner'],
    })
    def test_spam_detection_enabled(self):
        """Test spam detection when enabled."""
        # Test spam content
        self.assertTrue(check_content_for_spam("Buy viagra now!"))
        self.assertTrue(check_content_for_spam("You are the WINNER!"))
        self.assertTrue(check_content_for_spam("Visit our casino"))
        
        # Test clean content
        self.assertFalse(check_content_for_spam("This is a normal comment"))
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'SPAM_DETECTION_ENABLED': False,
    })
    def test_spam_detection_disabled(self):
        """Test that spam detection can be disabled."""
        # Even with spam words, should return False when disabled
        self.assertFalse(check_content_for_spam("Buy viagra now!"))
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'SPAM_DETECTION_ENABLED': True,
        'SPAM_WORDS': ['viagra'],
        'SPAM_ACTION': 'hide',
    })
    def test_spam_action_hide(self):
        """Test spam action 'hide' rejects content."""
        is_allowed, reason = is_comment_content_allowed("Buy viagra now!")
        self.assertFalse(is_allowed)
        self.assertIn('spam', reason.lower())
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'SPAM_DETECTION_ENABLED': True,
        'SPAM_WORDS': ['viagra'],
        'SPAM_ACTION': 'delete',
    })
    def test_spam_action_delete(self):
        """Test spam action 'delete' rejects content."""
        is_allowed, reason = is_comment_content_allowed("Buy viagra now!")
        self.assertFalse(is_allowed)
        self.assertIn('spam', reason.lower())
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'SPAM_DETECTION_ENABLED': True,
        'SPAM_WORDS': ['viagra'],
        'SPAM_ACTION': 'flag',
    })
    def test_spam_action_flag(self):
        """Test spam action 'flag' allows content but marks for flagging."""
        is_allowed, reason = is_comment_content_allowed("Buy viagra now!")
        # Content is allowed (will be flagged after creation)
        self.assertTrue(is_allowed)
        
        # Check that process_comment_content marks it for flagging
        _, flags = process_comment_content("Buy viagra now!")
        self.assertTrue(flags['is_spam'])
        self.assertTrue(flags['auto_flag_spam'])


class ProfanityFilteringTestCase(TestCase):
    """Test profanity filtering functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'PROFANITY_FILTERING': True,
        'PROFANITY_LIST': ['badword', 'offensive'],
    })
    def test_profanity_detection(self):
        """Test profanity detection."""
        self.assertTrue(check_content_for_profanity("This is badword content"))
        self.assertTrue(check_content_for_profanity("Very offensive comment"))
        self.assertFalse(check_content_for_profanity("This is clean content"))
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'PROFANITY_FILTERING': True,
        'PROFANITY_LIST': ['badword'],
        'PROFANITY_ACTION': 'censor',
    })
    def test_profanity_action_censor(self):
        """Test profanity censoring."""
        censored = filter_profanity("This is a badword comment")
        self.assertIn('*******', censored)
        self.assertNotIn('badword', censored)
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'PROFANITY_FILTERING': True,
        'PROFANITY_LIST': ['badword'],
        'PROFANITY_ACTION': 'hide',
    })
    def test_profanity_action_hide(self):
        """Test profanity action 'hide' rejects content."""
        is_allowed, reason = is_comment_content_allowed("This is a badword comment")
        self.assertFalse(is_allowed)
        self.assertIn('profanity', reason.lower())
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'PROFANITY_FILTERING': True,
        'PROFANITY_LIST': ['badword'],
        'PROFANITY_ACTION': 'delete',
    })
    def test_profanity_action_delete(self):
        """Test profanity action 'delete' rejects content."""
        is_allowed, reason = is_comment_content_allowed("This is a badword comment")
        self.assertFalse(is_allowed)
        self.assertIn('profanity', reason.lower())
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'PROFANITY_FILTERING': True,
        'PROFANITY_LIST': ['badword'],
        'PROFANITY_ACTION': 'flag',
    })
    def test_profanity_action_flag(self):
        """Test profanity action 'flag' allows but marks for flagging."""
        is_allowed, reason = is_comment_content_allowed("This is a badword comment")
        self.assertTrue(is_allowed)
        
        _, flags = process_comment_content("This is a badword comment")
        self.assertTrue(flags['has_profanity'])
        self.assertTrue(flags['auto_flag_profanity'])
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'PROFANITY_FILTERING': True,
        'PROFANITY_LIST': ['bad'],
    })
    def test_profanity_word_boundary(self):
        """Test that profanity detection respects word boundaries."""
        # 'bad' is in list, but 'badge' shouldn't match
        self.assertTrue(check_content_for_profanity("This is bad"))
        self.assertFalse(check_content_for_profanity("Nice badge"))


class AutomaticFlaggingTestCase(TestCase):
    """Test automatic flagging functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.content_type = ContentType.objects.get_for_model(User)
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'SPAM_DETECTION_ENABLED': True,
        'SPAM_WORDS': ['spam'],
        'SPAM_ACTION': 'flag',
    })
    def test_automatic_spam_flagging(self):
        """Test that spam comments are automatically flagged."""
        # Create comment with spam content
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_id=self.user.id,
            user=self.user,
            content="This is spam content"
        )
        
        # Apply automatic flags (normally done by signal)
        apply_automatic_flags(comment)
        
        # Verify comment was flagged
        flags = CommentFlag.objects.filter(
            comment_type=self.content_type,
            comment_id=str(comment.pk),
            flag='spam'
        )
        self.assertEqual(flags.count(), 1)
        self.assertEqual(flags.first().user.username, 'system')
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'PROFANITY_FILTERING': True,
        'PROFANITY_LIST': ['badword'],
        'PROFANITY_ACTION': 'flag',
    })
    def test_automatic_profanity_flagging(self):
        """Test that profane comments are automatically flagged."""
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_id=self.user.id,
            user=self.user,
            content="This contains badword"
        )
        
        apply_automatic_flags(comment)
        
        flags = CommentFlag.objects.filter(
            comment_type=self.content_type,
            comment_id=str(comment.pk),
            flag='offensive'
        )
        self.assertEqual(flags.count(), 1)
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'SPAM_DETECTION_ENABLED': True,
        'SPAM_WORDS': ['spam'],
        'SPAM_ACTION': 'flag',
        'PROFANITY_FILTERING': True,
        'PROFANITY_LIST': ['badword'],
        'PROFANITY_ACTION': 'flag',
    })
    def test_multiple_automatic_flags(self):
        """Test that both spam and profanity flags can be applied."""
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_id=self.user.id,
            user=self.user,
            content="This is spam with badword"
        )
        
        apply_automatic_flags(comment)
        
        # Should have both flags
        all_flags = CommentFlag.objects.filter(
            comment_type=self.content_type,
            comment_id=str(comment.pk)
        )
        self.assertEqual(all_flags.count(), 2)
        flag_types = set(all_flags.values_list('flag', flat=True))
        self.assertIn('spam', flag_types)
        self.assertIn('offensive', flag_types)


class ContentProcessingTestCase(TestCase):
    """Test complete content processing pipeline."""
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'PROFANITY_FILTERING': True,
        'PROFANITY_LIST': ['badword'],
        'PROFANITY_ACTION': 'censor',
    })
    def test_content_processing_with_censoring(self):
        """Test that content is properly censored during processing."""
        original = "This is a badword comment"
        processed, flags = process_comment_content(original)
        
        # Content should be censored
        self.assertNotIn('badword', processed)
        self.assertIn('*******', processed)
        
        # Flags should indicate profanity
        self.assertTrue(flags['has_profanity'])
        self.assertFalse(flags['auto_flag_profanity'])  # Censored, not flagged
    
    @override_settings(DJANGO_COMMENTS_CONFIG={
        'SPAM_DETECTION_ENABLED': True,
        'SPAM_WORDS': ['spam'],
        'SPAM_ACTION': 'flag',
        'PROFANITY_FILTERING': True,
        'PROFANITY_LIST': ['badword'],
        'PROFANITY_ACTION': 'censor',
    })
    def test_content_processing_combined(self):
        """Test processing with both spam and profanity."""
        original = "This spam message has badword"
        processed, flags = process_comment_content(original)
        
        # Profanity should be censored
        self.assertNotIn('badword', processed)
        
        # Spam should be flagged for flagging
        self.assertTrue(flags['is_spam'])
        self.assertTrue(flags['auto_flag_spam'])
        
        # Profanity detected but censored
        self.assertTrue(flags['has_profanity'])
        self.assertFalse(flags['auto_flag_profanity'])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])