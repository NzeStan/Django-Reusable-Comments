import uuid
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class BaseCommentTestCase(TestCase):
    """
    Base test case with common setup and fixtures for all comment tests.
    
    Provides:
    - Standard test users (regular user, moderator, admin, staff)
    - Test article model setup
    - Helper methods for creating comments, flags, bans, etc.
    - Assertion helpers for common checks
    """
    
    @classmethod
    def setUpTestData(cls):
        """
        Set up test data once for the entire test class.
        This data is not modified during tests (read-only).
        """
        # Create test users with different permission levels
        cls.regular_user = User.objects.create_user(
            username='john_doe',
            email='john@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        
        cls.moderator = User.objects.create_user(
            username='jane_moderator',
            email='jane@example.com',
            password='testpass123',
            first_name='Jane',
            last_name='Smith',
            is_staff=True
        )
        
        cls.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        cls.staff_user = User.objects.create_user(
            username='staff_member',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )
        
        # Create another regular user for multi-user tests
        cls.another_user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='testpass123',
            first_name='Alice',
            last_name='Johnson'
        )
        
        # Create a banned user
        cls.banned_user = User.objects.create_user(
            username='banned',
            email='banned@example.com',
            password='testpass123'
        )
        
    def setUp(self):
        """
        Set up test data before each test method.
        This data can be modified during tests.
        """
        # Import models here to avoid circular imports
        from django_comments.models import Comment, CommentFlag, BannedUser
        
        self.Comment = Comment
        self.CommentFlag = CommentFlag
        self.BannedUser = BannedUser
        
        # Create a test content type (using User model as commented object)
        self.content_type = ContentType.objects.get_for_model(User)
        
        # Create test object to comment on
        self.test_obj = self.regular_user
        self.test_obj_id = str(self.test_obj.pk)
        
    
    def create_comment(self, **kwargs):
        """
        Helper to create a comment with sensible defaults.
        
        Args:
            **kwargs: Override default comment fields
        
        Returns:
            Comment instance
        """
        defaults = {
            'content_type': self.content_type,
            'object_id': self.test_obj_id,
            'user': self.regular_user,
            'content': 'This is a test comment with real-world content.',
            'is_public': True,
            'is_removed': False,
        }
        defaults.update(kwargs)
        return self.Comment.objects.create(**defaults)
    
    def create_comment_tree(self, depth=3, children_per_level=2):
        """
        Create a tree of nested comments for threading tests.
        
        Args:
            depth: How many levels deep
            children_per_level: How many replies at each level
            
        Returns:
            List of all created comments
        """
        comments = []
        root = self.create_comment(content='Root comment')
        comments.append(root)
        
        def create_children(parent, current_depth):
            if current_depth >= depth:
                return
            
            for i in range(children_per_level):
                child = self.create_comment(
                    parent=parent,
                    content=f'Reply at depth {current_depth + 1}, child {i + 1}'
                )
                comments.append(child)
                create_children(child, current_depth + 1)
        
        create_children(root, 0)
        return comments
    
    def create_anonymous_comment(self, **kwargs):
        """Create an anonymous comment (no user)."""
        defaults = {
            'user': None,
            'user_name': 'Anonymous User',
            'user_email': 'anonymous@example.com',
        }
        defaults.update(kwargs)
        return self.create_comment(**defaults)

    
    def create_flag(self, comment=None, **kwargs):
        """
        Helper to create a comment flag with sensible defaults.
        
        Args:
            comment: Comment to flag (creates one if None)
            **kwargs: Override default flag fields
            
        Returns:
            CommentFlag instance
        """
        if comment is None:
            comment = self.create_comment()

        # Flags must reference the Comment model's ContentType, not the commented-on object's CT
        comment_ct = ContentType.objects.get_for_model(self.Comment)

        defaults = {
            'comment_type': comment_ct,
            'comment_id': str(comment.pk),
            'user': self.moderator,
            'flag': 'spam',
            'reason': 'This looks like spam content',
        }
        defaults.update(kwargs)
        return self.CommentFlag.objects.create(**defaults)
    
    # ========================================================================
    # HELPER METHODS - Ban Creation
    # ========================================================================
    
    def create_ban(self, user=None, **kwargs):
        """
        Helper to create a user ban with sensible defaults.
        
        Args:
            user: User to ban (uses banned_user if None)
            **kwargs: Override default ban fields
            
        Returns:
            BannedUser instance
        """
        if user is None:
            user = self.banned_user
        
        defaults = {
            'user': user,
            'reason': 'Repeated violations of community guidelines',
            'banned_by': self.moderator,
        }
        defaults.update(kwargs)
        return self.BannedUser.objects.create(**defaults)
    
    def create_temporary_ban(self, user=None, days=7, **kwargs):
        """Create a temporary ban that expires in X days."""
        kwargs['banned_until'] = timezone.now() + timedelta(days=days)
        return self.create_ban(user=user, **kwargs)
    
    def create_expired_ban(self, user=None, **kwargs):
        """Create a ban that has already expired."""
        kwargs['banned_until'] = timezone.now() - timedelta(days=1)
        return self.create_ban(user=user, **kwargs)
    
    # ========================================================================
    # HELPER METHODS - Assertions
    # ========================================================================
    
    def assertCommentValid(self, comment):
        """Assert that a comment is valid and saved properly."""
        self.assertIsNotNone(comment.pk)
        self.assertIsInstance(comment.pk, uuid.UUID)
        self.assertIsNotNone(comment.created_at)
        self.assertIsNotNone(comment.updated_at)
        self.assertIsNotNone(comment.content)
        self.assertGreater(len(comment.content), 0)
    
    def assertCommentPublic(self, comment):
        """Assert that a comment is public and not removed."""
        self.assertTrue(comment.is_public)
        self.assertFalse(comment.is_removed)
    
    def assertCommentNotPublic(self, comment):
        """Assert that a comment is not public or is removed."""
        self.assertTrue(not comment.is_public or comment.is_removed)
    
    def assertFlagValid(self, flag):
        """Assert that a flag is valid and saved properly."""
        self.assertIsNotNone(flag.pk)
        self.assertIsInstance(flag.pk, uuid.UUID)
        self.assertIsNotNone(flag.created_at)
        self.assertIsNotNone(flag.flag)
        self.assertIn(flag.flag, dict(self.CommentFlag.FLAG_CHOICES).keys())
    
    def assertBanActive(self, ban):
        """Assert that a ban is currently active."""
        self.assertTrue(ban.is_active)
        if ban.banned_until:
            self.assertGreater(ban.banned_until, timezone.now())
    
    def assertBanExpired(self, ban):
        """Assert that a ban has expired."""
        self.assertFalse(ban.is_active)
        if ban.banned_until:
            self.assertLess(ban.banned_until, timezone.now())
    
    # ========================================================================
    # HELPER METHODS - Database Queries
    # ========================================================================
    
    def get_fresh_comment(self, comment):
        """Reload comment from database to get fresh data."""
        return self.Comment.objects.get(pk=comment.pk)
    
    def get_fresh_flag(self, flag):
        """Reload flag from database to get fresh data."""
        return self.CommentFlag.objects.get(pk=flag.pk)
    
    def get_fresh_ban(self, ban):
        """Reload ban from database to get fresh data."""
        return self.BannedUser.objects.get(pk=ban.pk)
    
    # ========================================================================
    # HELPER METHODS - Cleanup
    # ========================================================================
    
    def cleanup_comments(self):
        """Delete all comments created during the test."""
        self.Comment.objects.all().delete()
    
    def cleanup_flags(self):
        """Delete all flags created during the test."""
        self.CommentFlag.objects.all().delete()
    
    def cleanup_bans(self):
        """Delete all bans created during the test."""
        self.BannedUser.objects.all().delete()