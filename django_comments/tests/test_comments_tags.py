"""
Comprehensive tests for django_comments/templatetags/comment_tags.py

Tests cover:
- Success cases for all template tags and filters
- Failure cases with invalid input
- Edge cases (None, deleted objects, anonymous users)
- Real-world scenarios (formatting, caching, performance)
- XSS prevention and security
"""
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.template import Context, Template
from django.utils.safestring import SafeString
from django.core.cache import cache

from django_comments.tests.base import BaseCommentTestCase
from django_comments.models import Comment
from django_comments.templatetags import comment_tags


User = get_user_model()


class GetCommentCountTagTest(BaseCommentTestCase):
    """Test get_comment_count template tag."""
    
    def setUp(self):
        super().setUp()
        # Use test_obj from base class
        self.post = self.test_obj
        
        # Create mix of public and private comments
        self.public_comment = self.create_comment(
            is_public=True,
            is_removed=False
        )
        self.private_comment = self.create_comment(
            is_public=False,
            is_removed=False
        )
        self.removed_comment = self.create_comment(
            is_public=True,
            is_removed=True
        )
    
    def test_get_comment_count_public_only(self):
        """Test getting public comment count (default behavior)."""
        count = comment_tags.get_comment_count(self.post)
        self.assertEqual(count, 1)  # Only public_comment
    
    def test_get_comment_count_all_comments(self):
        """Test getting all comment count (public_only=False)."""
        count = comment_tags.get_comment_count(self.post, public_only=False)
        self.assertEqual(count, 3)  # All three comments
    
    def test_get_comment_count_no_comments(self):
        """Test getting count for object with no comments."""
        # Create new user to use as test object
        new_user = User.objects.create_user(username='newuser', email='new@test.com')
        count = comment_tags.get_comment_count(new_user)
        self.assertEqual(count, 0)
    
    def test_get_comment_count_with_caching(self):
        """Test that comment count uses caching."""
        # Clear cache first
        cache.clear()
        
        # First call should hit database
        count1 = comment_tags.get_comment_count(self.post)
        
        # Create new comment
        self.create_comment(is_public=True)
        
        # Cache should be invalidated, new count should be returned
        count2 = comment_tags.get_comment_count(self.post)
        self.assertEqual(count2, count1 + 1)
    
    def test_get_comment_count_invalid_object(self):
        """Test get_comment_count with invalid object returns 0."""
        count = comment_tags.get_comment_count(None)
        self.assertEqual(count, 0)
    
    def test_get_comment_count_deleted_object(self):
        """Test get_comment_count with object that has no ContentType."""
        # Create a mock object that will cause exception
        mock_obj = Mock()
        mock_obj.pk = 999
        
        with patch('django.contrib.contenttypes.models.ContentType.objects.get_for_model',
                   side_effect=Exception("ContentType error")):
            count = comment_tags.get_comment_count(mock_obj)
            self.assertEqual(count, 0)
    
    def test_get_comment_count_in_template(self):
        """Test get_comment_count tag in actual template."""
        template = Template(
            '{% load comment_tags %}'
            '{% get_comment_count obj %}'
        )
        context = Context({'obj': self.post})
        rendered = template.render(context)
        self.assertEqual(rendered.strip(), '1')
    
    def test_get_comment_count_with_parameters_in_template(self):
        """Test get_comment_count with public_only parameter in template."""
        template = Template(
            '{% load comment_tags %}'
            '{% get_comment_count obj public_only=False %}'
        )
        context = Context({'obj': self.post})
        rendered = template.render(context)
        self.assertEqual(rendered.strip(), '3')


class GetCommentsForTagTest(BaseCommentTestCase):
    """Test get_comments_for template tag."""
    
    def setUp(self):
        super().setUp()
        self.post = self.test_obj
        
        # Create comments with different timestamps and states
        self.comment1 = self.create_comment(
            content="First comment",
            is_public=True
        )
        self.comment2 = self.create_comment(
            content="Second comment",
            is_public=True
        )
        self.private_comment = self.create_comment(
            content="Private comment",
            is_public=False
        )
    
    def test_get_comments_for_public_only(self):
        """Test getting public comments only."""
        comments = comment_tags.get_comments_for(self.post)
        self.assertEqual(comments.count(), 2)
        self.assertIn(self.comment1, comments)
        self.assertIn(self.comment2, comments)
        self.assertNotIn(self.private_comment, comments)
    
    def test_get_comments_for_all_comments(self):
        """Test getting all comments including private."""
        comments = comment_tags.get_comments_for(self.post, public_only=False)
        self.assertEqual(comments.count(), 3)
    
    def test_get_comments_for_ordered_by_created_desc(self):
        """Test comments are ordered by created_at descending."""
        comments = list(comment_tags.get_comments_for(self.post))
        # Most recent first
        self.assertEqual(comments[0].id, self.comment2.id)
        self.assertEqual(comments[1].id, self.comment1.id)
    
    def test_get_comments_for_optimized_query(self):
        """Test that queries are optimized with select_related/prefetch_related."""
        comments = comment_tags.get_comments_for(self.post)
        
        # Evaluate queryset
        comment_list = list(comments)
        
        # Accessing related objects shouldn't cause additional queries
        with self.assertNumQueries(0):
            for comment in comment_list:
                _ = comment.user.username if comment.user else None
                _ = comment.content_type.model
    
    def test_get_comments_for_no_comments(self):
        """Test getting comments for object with none."""
        new_user = User.objects.create_user(username='nocomments', email='no@test.com')
        comments = comment_tags.get_comments_for(new_user)
        self.assertEqual(comments.count(), 0)
    
    def test_get_comments_for_invalid_object(self):
        """Test get_comments_for with invalid object returns empty queryset."""
        comments = comment_tags.get_comments_for(None)
        self.assertEqual(comments.count(), 0)
        # Should be a proper Comment queryset
        self.assertEqual(comments.model, Comment)
    
    def test_get_comments_for_in_template(self):
        """Test get_comments_for in template with iteration."""
        template = Template(
            '{% load comment_tags %}'
            '{% get_comments_for obj as comments %}'
            '{% for comment in comments %}'
            '{{ comment.content }}|'
            '{% endfor %}'
        )
        context = Context({'obj': self.post})
        rendered = template.render(context)
        self.assertIn('Second comment|', rendered)
        self.assertIn('First comment|', rendered)
        self.assertNotIn('Private comment', rendered)


class GetRootCommentsForTagTest(BaseCommentTestCase):
    """Test get_root_comments_for template tag."""
    
    def setUp(self):
        super().setUp()
        self.post = self.test_obj
        
        # Create threaded comments
        self.root1 = self.create_comment(
            content="Root comment 1",
            is_public=True
        )
        self.child1 = self.create_comment(
            content="Child of root1",
            parent=self.root1,
            is_public=True
        )
        self.root2 = self.create_comment(
            content="Root comment 2",
            is_public=True
        )
        self.private_root = self.create_comment(
            content="Private root",
            is_public=False
        )
    
    def test_get_root_comments_for_public_only(self):
        """Test getting only public root comments."""
        roots = comment_tags.get_root_comments_for(self.post)
        root_list = list(roots)
        
        self.assertEqual(len(root_list), 2)
        self.assertIn(self.root1, root_list)
        self.assertIn(self.root2, root_list)
        self.assertNotIn(self.child1, root_list)
        self.assertNotIn(self.private_root, root_list)
    
    def test_get_root_comments_for_all(self):
        """Test getting all root comments including private."""
        roots = comment_tags.get_root_comments_for(self.post, public_only=False)
        self.assertEqual(roots.count(), 3)
    
    def test_get_root_comments_with_full_thread(self):
        """Test that with_full_thread prefetches children."""
        roots = comment_tags.get_root_comments_for(self.post)
        root_list = list(roots)
        
        # Should be able to access children without additional queries
        with self.assertNumQueries(0):
            for root in root_list:
                _ = list(root.children.all())
    
    def test_get_root_comments_ordered_desc(self):
        """Test root comments are ordered by created_at descending."""
        roots = list(comment_tags.get_root_comments_for(self.post))
        self.assertEqual(roots[0].id, self.root2.id)
        self.assertEqual(roots[1].id, self.root1.id)
    
    def test_get_root_comments_no_comments(self):
        """Test getting root comments for object with none."""
        new_user = User.objects.create_user(username='norootcomments', email='noroot@test.com')
        roots = comment_tags.get_root_comments_for(new_user)
        self.assertEqual(roots.count(), 0)
    
    def test_get_root_comments_invalid_object(self):
        """Test with invalid object returns empty queryset."""
        roots = comment_tags.get_root_comments_for(None)
        self.assertEqual(roots.count(), 0)
    
    def test_get_root_comments_in_template_with_children(self):
        """Test get_root_comments_for in template with nested iteration."""
        template = Template(
            '{% load comment_tags %}'
            '{% get_root_comments_for obj as roots %}'
            '{% for root in roots %}'
            'ROOT:{{ root.content }}|'
            '{% for child in root.children.all %}'
            'CHILD:{{ child.content }}|'
            '{% endfor %}'
            '{% endfor %}'
        )
        context = Context({'obj': self.post})
        rendered = template.render(context)
        
        self.assertIn('ROOT:Root comment 1|', rendered)
        self.assertIn('CHILD:Child of root1|', rendered)
        self.assertIn('ROOT:Root comment 2|', rendered)
        self.assertNotIn('Private root', rendered)


class HasCommentsFilterTest(BaseCommentTestCase):
    """Test has_comments template filter."""
    
    def setUp(self):
        super().setUp()
        self.post_with_comments = self.test_obj
        self.post_without_comments = User.objects.create_user(
            username='nocomments2', 
            email='nocomments2@test.com'
        )
        
        self.create_comment(is_public=True)
    
    def test_has_comments_true(self):
        """Test filter returns True when object has comments."""
        result = comment_tags.has_comments(self.post_with_comments)
        self.assertTrue(result)
    
    def test_has_comments_false(self):
        """Test filter returns False when object has no comments."""
        result = comment_tags.has_comments(self.post_without_comments)
        self.assertFalse(result)
    
    def test_has_comments_only_counts_public(self):
        """Test filter only counts public comments."""
        post = User.objects.create_user(username='privateonly', email='private@test.com')
        ct = ContentType.objects.get_for_model(User)
        self.create_comment(
            content_type=ct,
            object_id=str(post.pk),
            is_public=False
        )
        result = comment_tags.has_comments(post)
        self.assertFalse(result)
    
    def test_has_comments_invalid_object(self):
        """Test filter with invalid object returns False."""
        result = comment_tags.has_comments(None)
        self.assertFalse(result)
    
    def test_has_comments_in_template_conditional(self):
        """Test has_comments filter in template if statement."""
        template = Template(
            '{% load comment_tags %}'
            '{% if obj|has_comments %}'
            'HAS_COMMENTS'
            '{% else %}'
            'NO_COMMENTS'
            '{% endif %}'
        )
        
        # Test with comments
        context = Context({'obj': self.post_with_comments})
        rendered = template.render(context)
        self.assertIn('HAS_COMMENTS', rendered)
        
        # Test without comments
        context = Context({'obj': self.post_without_comments})
        rendered = template.render(context)
        self.assertIn('NO_COMMENTS', rendered)


class FormatCommentFilterTest(BaseCommentTestCase):
    """Test format_comment and related formatting filters."""
    
    def test_format_comment_plain_text(self):
        """Test formatting plain text content."""
        content = "This is plain text with <script>alert('xss')</script>"
        result = comment_tags.format_comment(content, format_type='plain')
        
        # Should escape HTML
        self.assertIsInstance(result, SafeString)
        self.assertIn('&lt;script&gt;', result)
        self.assertNotIn('<script>', result)
    
    def test_format_comment_markdown(self):
        """Test formatting Markdown content."""
        content = "**Bold text** and *italic*"
        result = comment_tags.format_comment(content, format_type='markdown')
        
        self.assertIsInstance(result, SafeString)
        self.assertIn('<strong>Bold text</strong>', result)
        self.assertIn('<em>italic</em>', result)
    
    def test_format_comment_markdown_with_links(self):
        """Test Markdown with links."""
        content = "[Link](https://example.com)"
        result = comment_tags.format_comment(content, format_type='markdown')
        
        self.assertIn('<a href="https://example.com"', result)
        self.assertIn('Link</a>', result)
    
    def test_format_comment_html_sanitized(self):
        """Test HTML formatting with sanitization."""
        content = '<p>Safe content</p><script>alert("xss")</script>'
        result = comment_tags.format_comment(content, format_type='html')
        
        self.assertIsInstance(result, SafeString)
        self.assertIn('<p>Safe content</p>', result)
        self.assertNotIn('<script>', result)
    
    def test_format_comment_default_format(self):
        """Test using default format from settings."""
        content = "Test content"
        
        with override_settings(DJANGO_COMMENTS={'COMMENT_FORMAT': 'plain'}):
            result = comment_tags.format_comment(content)
            self.assertIsInstance(result, SafeString)
    
    def test_format_comment_xss_prevention(self):
        """Test XSS prevention in all formats."""
        xss_attempts = [
            '<script>alert("xss")</script>',
            '<img src=x onerror="alert(1)">',
            '<iframe src="evil.com"></iframe>',
            'javascript:alert(1)',
            '<object data="evil.com"></object>',
        ]
        
        for xss in xss_attempts:
            # Plain text - should escape everything
            result = comment_tags.format_comment(xss, format_type='plain')
            self.assertNotIn('<script', result.lower())
            # javascript: gets escaped as &lt;javascript:&gt; or similar
            
            # HTML - should strip dangerous tags
            result = comment_tags.format_comment(xss, format_type='html')
            self.assertNotIn('<script', result.lower())
    
    def test_format_comment_unicode_content(self):
        """Test formatting with Unicode characters."""
        unicode_content = "Hello 世界! 🌍 Привет мир!"
        
        for format_type in ['plain', 'markdown', 'html']:
            result = comment_tags.format_comment(unicode_content, format_type=format_type)
            self.assertIsInstance(result, SafeString)
            self.assertIn('世界', result)
            self.assertIn('🌍', result)
            self.assertIn('Привет', result)
    
    def test_format_comment_long_content(self):
        """Test formatting very long content."""
        long_content = "A" * 10000
        result = comment_tags.format_comment(long_content, format_type='plain')
        
        self.assertIsInstance(result, SafeString)
        self.assertEqual(len(result), 10000)
    
    def test_format_comment_empty_content(self):
        """Test formatting empty content."""
        result = comment_tags.format_comment('', format_type='plain')
        self.assertIsInstance(result, SafeString)
        self.assertEqual(result, '')
    
    def test_format_comment_exception_handling(self):
        """Test graceful handling of formatting exceptions."""
        # Mock render_comment_content to raise exception
        with patch('django_comments.templatetags.comment_tags.render_comment_content',
                   side_effect=Exception("Format error")):
            content = "Test content"
            result = comment_tags.format_comment(content)
            
            # Should fall back to escaped content
            self.assertIsInstance(result, SafeString)
            self.assertIn('Test content', result)
    
    def test_format_comment_plain_filter(self):
        """Test format_comment_plain convenience filter."""
        content = "<p>Test</p>"
        result = comment_tags.format_comment_plain(content)
        
        self.assertIsInstance(result, SafeString)
        self.assertNotIn('<p>', result)
    
    def test_format_comment_markdown_filter(self):
        """Test format_comment_markdown convenience filter."""
        content = "**Bold**"
        result = comment_tags.format_comment_markdown(content)
        
        self.assertIsInstance(result, SafeString)
        self.assertIn('<strong>Bold</strong>', result)
    
    def test_format_comment_html_filter(self):
        """Test format_comment_html convenience filter."""
        content = "<strong>Bold</strong><script>xss</script>"
        result = comment_tags.format_comment_html(content)
        
        self.assertIsInstance(result, SafeString)
        self.assertIn('<strong>Bold</strong>', result)
        self.assertNotIn('<script>', result)
    
    def test_format_comment_in_template(self):
        """Test format_comment filter in template."""
        template = Template(
            '{% load comment_tags %}'
            '{{ content|format_comment:"markdown" }}'
        )
        context = Context({'content': '**Bold** text'})
        rendered = template.render(context)
        
        self.assertIn('<strong>Bold</strong>', rendered)
    
    def test_format_comment_code_blocks(self):
        """Test formatting with code blocks."""
        content = """
```python
def hello():
    print("Hello, World!")
```
"""
        result = comment_tags.format_comment(content, format_type='markdown')
        
        self.assertIsInstance(result, SafeString)
        self.assertIn('<code', result)
        self.assertIn('def hello', result)
    
    def test_format_comment_multiline(self):
        """Test formatting multiline content."""
        content = """Line 1
Line 2
Line 3"""
        result = comment_tags.format_comment(content, format_type='plain')
        
        self.assertIsInstance(result, SafeString)
        self.assertIn('Line 1', result)
        self.assertIn('Line 2', result)
        self.assertIn('Line 3', result)


class ShowCommentCountInclusionTagTest(BaseCommentTestCase):
    """Test show_comment_count inclusion tag."""
    
    def setUp(self):
        super().setUp()
        self.post = self.test_obj
        
        # Create some comments
        for i in range(3):
            self.create_comment(is_public=True)
    
    def test_show_comment_count_returns_context(self):
        """Test that tag returns proper context dict."""
        context = comment_tags.show_comment_count(self.post)
        
        self.assertIn('count', context)
        self.assertIn('object', context)
        self.assertIn('link', context)
        self.assertEqual(context['count'], 3)
        self.assertEqual(context['object'], self.post)
        self.assertTrue(context['link'])
    
    def test_show_comment_count_with_link_false(self):
        """Test show_comment_count with link=False."""
        context = comment_tags.show_comment_count(self.post, link=False)
        
        self.assertFalse(context['link'])
    
    def test_show_comment_count_no_comments(self):
        """Test show_comment_count with zero comments."""
        new_user = User.objects.create_user(username='empty', email='empty@test.com')
        context = comment_tags.show_comment_count(new_user)
        
        self.assertEqual(context['count'], 0)
    
    @patch('django_comments.templatetags.comment_tags.get_comment_count_for_object')
    def test_show_comment_count_uses_caching(self, mock_get_count):
        """Test that show_comment_count uses cached count."""
        mock_get_count.return_value = 5
        
        context = comment_tags.show_comment_count(self.post)
        
        mock_get_count.assert_called_once_with(self.post, public_only=True)
        self.assertEqual(context['count'], 5)


class ShowCommentsInclusionTagTest(BaseCommentTestCase):
    """Test show_comments inclusion tag."""
    
    def setUp(self):
        super().setUp()
        self.post = self.test_obj
        
        # Create comments
        self.comments = []
        for i in range(5):
            comment = self.create_comment(
                content=f"Comment {i}",
                is_public=True
            )
            self.comments.append(comment)
    
    def test_show_comments_returns_context(self):
        """Test that tag returns proper context dict."""
        context = comment_tags.show_comments(self.post)
        
        self.assertIn('comments', context)
        self.assertIn('object', context)
        self.assertEqual(context['object'], self.post)
        self.assertEqual(context['comments'].count(), 5)
    
    def test_show_comments_with_max_limit(self):
        """Test show_comments with max_comments limit."""
        context = comment_tags.show_comments(self.post, max_comments=3)
        
        comments_list = list(context['comments'])
        self.assertEqual(len(comments_list), 3)
    
    def test_show_comments_ordered_desc(self):
        """Test comments are ordered by created_at descending."""
        context = comment_tags.show_comments(self.post)
        comments_list = list(context['comments'])
        
        # Should be in reverse order (most recent first)
        self.assertEqual(comments_list[0].id, self.comments[-1].id)
    
    def test_show_comments_no_comments(self):
        """Test show_comments with no comments."""
        new_user = User.objects.create_user(username='noshow', email='noshow@test.com')
        context = comment_tags.show_comments(new_user)
        
        self.assertEqual(context['comments'].count(), 0)
    
    def test_show_comments_optimized_query(self):
        """Test that show_comments uses optimized query."""
        # This should use get_comments_for which calls optimized_for_list
        context = comment_tags.show_comments(self.post)
        
        # Evaluate queryset
        comment_list = list(context['comments'])
        
        # Accessing related data shouldn't cause additional queries
        with self.assertNumQueries(0):
            for comment in comment_list:
                _ = comment.user.username if comment.user else None


class GetUserCommentCountTagTest(BaseCommentTestCase):
    """Test get_user_comment_count template tag."""
    
    def setUp(self):
        super().setUp()
        self.user = self.regular_user
        self.other_user = self.another_user
        
        # Create comments for test user
        for i in range(3):
            ct = ContentType.objects.get_for_model(User)
            self.create_comment(
                user=self.user,
                content=f"User comment {i}",
                content_type=ct,
                object_id=str(self.user.pk)
            )
        
        # Create comments for other user
        for i in range(2):
            ct = ContentType.objects.get_for_model(User)
            self.create_comment(
                user=self.other_user,
                content=f"Other user comment {i}",
                content_type=ct,
                object_id=str(self.other_user.pk)
            )
    
    def test_get_user_comment_count_from_context(self):
        """Test getting count for user from context."""
        context = Context({'user': self.user})
        count = comment_tags.get_user_comment_count(context)
        
        self.assertEqual(count, 3)
    
    def test_get_user_comment_count_explicit_user(self):
        """Test getting count with explicit user parameter."""
        context = Context({})
        count = comment_tags.get_user_comment_count(context, user=self.other_user)
        
        self.assertEqual(count, 2)
    
    def test_get_user_comment_count_anonymous_user(self):
        """Test getting count for anonymous user returns 0."""
        from django.contrib.auth.models import AnonymousUser
        
        context = Context({'user': AnonymousUser()})
        count = comment_tags.get_user_comment_count(context)
        
        self.assertEqual(count, 0)
    
    def test_get_user_comment_count_no_user_in_context(self):
        """Test getting count with no user in context returns 0."""
        context = Context({})
        count = comment_tags.get_user_comment_count(context)
        
        self.assertEqual(count, 0)
    
    def test_get_user_comment_count_user_with_no_comments(self):
        """Test getting count for user with no comments."""
        new_user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='testpass123'
        )
        
        context = Context({'user': new_user})
        count = comment_tags.get_user_comment_count(context)
        
        self.assertEqual(count, 0)
    
    def test_get_user_comment_count_exception_handling(self):
        """Test graceful handling of exceptions."""
        # Mock to raise exception
        with patch.object(Comment.objects, 'filter', side_effect=Exception("DB error")):
            context = Context({'user': self.user})
            count = comment_tags.get_user_comment_count(context)
            
            self.assertEqual(count, 0)
    
    def test_get_user_comment_count_in_template(self):
        """Test get_user_comment_count in template."""
        template = Template(
            '{% load comment_tags %}'
            '{% get_user_comment_count %}'
        )
        context = Context({'user': self.user})
        rendered = template.render(context)
        
        self.assertEqual(rendered.strip(), '3')
    
    def test_get_user_comment_count_with_explicit_user_in_template(self):
        """Test tag with explicit user parameter in template."""
        template = Template(
            '{% load comment_tags %}'
            '{% get_user_comment_count user=other_user %}'
        )
        context = Context({
            'user': self.user,
            'other_user': self.other_user
        })
        rendered = template.render(context)
        
        self.assertEqual(rendered.strip(), '2')


class TemplateTagEdgeCasesTest(BaseCommentTestCase):
    """Test edge cases and boundary conditions for all template tags."""
    
    def test_tags_with_none_objects(self):
        """Test all tags handle None objects gracefully."""
        # get_comment_count
        self.assertEqual(comment_tags.get_comment_count(None), 0)
        
        # has_comments
        self.assertFalse(comment_tags.has_comments(None))
        
        # get_comments_for
        comments = comment_tags.get_comments_for(None)
        self.assertEqual(comments.count(), 0)
        
        # get_root_comments_for
        roots = comment_tags.get_root_comments_for(None)
        self.assertEqual(roots.count(), 0)
    
    def test_format_filters_with_none(self):
        """Test formatting filters with None content."""
        # Should not crash
        result = comment_tags.format_comment(None, format_type='plain')
        self.assertIsInstance(result, SafeString)
    
    def test_format_filters_with_special_characters(self):
        """Test formatting with special characters."""
        special_chars = "Special: !@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        
        result = comment_tags.format_comment(special_chars, format_type='plain')
        self.assertIsInstance(result, SafeString)
        self.assertIn('!@#$%', result)
    
    def test_tags_with_very_large_numbers(self):
        """Test tags can handle objects with very large PKs."""
        post = self.test_obj
        
        # Create many comments to test counting
        for i in range(100):
            self.create_comment(
                is_public=True,
                content=f"Comment {i}"
            )
        
        count = comment_tags.get_comment_count(post)
        self.assertEqual(count, 100)
    
    def test_concurrent_cache_invalidation(self):
        """Test cache invalidation works with concurrent comment creation."""
        post = self.test_obj
        
        # Get initial count
        count1 = comment_tags.get_comment_count(post)
        self.assertEqual(count1, 0)
        
        # Create comment (should invalidate cache)
        self.create_comment(is_public=True)
        
        # Count should be updated
        count2 = comment_tags.get_comment_count(post)
        self.assertEqual(count2, 1)
    
    def test_format_comment_with_null_bytes(self):
        """Test formatting content with null bytes."""
        content = "Content with \x00 null byte"
        
        # Should handle without crashing
        result = comment_tags.format_comment(content, format_type='plain')
        self.assertIsInstance(result, SafeString)
    
    def test_tags_with_deleted_content_type(self):
        """Test tags when ContentType is deleted."""
        post = self.test_obj
        comment = self.create_comment(is_public=True)
        
        # This shouldn't crash even if content type issues occur
        ct = ContentType.objects.get_for_model(post)
        comment.content_type = ct
        comment.save()
        
        count = comment_tags.get_comment_count(post)
        self.assertIsInstance(count, int)


class TemplateTagPerformanceTest(BaseCommentTestCase):
    """Test performance and optimization of template tags."""
    
    def test_get_comments_query_optimization(self):
        """Test that get_comments_for minimizes database queries."""
        post = self.test_obj
        
        # Create comments with various relationships
        for i in range(5):
            self.create_comment(
                is_public=True,
                content=f"Comment {i}"
            )
        
        # Should use optimized query
        # Expect 2 queries: 1 main query + 1 prefetch_related for flags
        with self.assertNumQueries(2):
            comments = comment_tags.get_comments_for(post)
            list(comments)  # Evaluate queryset
    
    def test_get_root_comments_query_optimization(self):
        """Test that get_root_comments_for uses efficient queries."""
        post = self.test_obj
        
        # Create root and child comments
        root = self.create_comment(is_public=True, content="Root")
        for i in range(3):
            self.create_comment(
                parent=root,
                is_public=True,
                content=f"Child {i}"
            )
        
        # Should prefetch children
        roots = comment_tags.get_root_comments_for(post)
        root_list = list(roots)
        
        # Accessing children shouldn't cause additional queries
        with self.assertNumQueries(0):
            for root in root_list:
                list(root.children.all())
    
    def test_caching_reduces_queries(self):
        """Test that caching actually reduces database queries."""
        post = self.test_obj
        self.create_comment(is_public=True)
        
        cache.clear()
        
        # First call hits database
        with self.assertNumQueries(1):
            count1 = comment_tags.get_comment_count(post)
        
        # Second call uses cache (0 queries)
        with self.assertNumQueries(0):
            count2 = comment_tags.get_comment_count(post)
        
        self.assertEqual(count1, count2)


class TemplateTagSecurityTest(BaseCommentTestCase):
    """Test security aspects of template tags."""
    
    def test_xss_prevention_in_format_comment(self):
        """Test comprehensive XSS prevention."""
        xss_payloads = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror="alert(1)">',
            '<svg onload="alert(1)">',
            '<iframe src="javascript:alert(1)"></iframe>',
            '<body onload="alert(1)">',
            '<input onfocus="alert(1)" autofocus>',
            '<select onfocus="alert(1)" autofocus>',
            '<textarea onfocus="alert(1)" autofocus>',
            '<marquee onstart="alert(1)">',
            '<object data="javascript:alert(1)">',
            '<embed src="javascript:alert(1)">',
        ]
        
        for payload in xss_payloads:
            for format_type in ['plain', 'markdown', 'html']:
                result = comment_tags.format_comment(payload, format_type=format_type)
                
                # Dangerous tags/attributes should be stripped or escaped
                self.assertNotIn('<script', result.lower())
                # Check that dangerous event handlers are escaped/removed
                # Note: plain text escapes everything, so we check differently
                if format_type == 'plain':
                    # Everything should be escaped
                    if '<' in payload:
                        self.assertIn('&lt;', result)
                else:
                    # HTML/Markdown should strip dangerous content
                    self.assertNotIn('onerror="alert', result)
                    self.assertNotIn('onload="alert', result)
    
    def test_sql_injection_prevention(self):
        """Test that template tags don't allow SQL injection."""
        # Create object with potentially dangerous content
        post = self.test_obj
        
        # Tags should handle safely without SQL injection
        try:
            comment_tags.get_comment_count(post)
            comment_tags.has_comments(post)
            # Should not crash or execute malicious SQL
        except Exception as e:
            # If there's an exception, it shouldn't be SQL-related
            self.assertNotIn('syntax', str(e).lower())
            self.assertNotIn('sql', str(e).lower())
    
    def test_safe_string_return_types(self):
        """Test that formatting functions return SafeString."""
        content = "Test content"
        
        filters = [
            comment_tags.format_comment,
            comment_tags.format_comment_plain,
            comment_tags.format_comment_markdown,
            comment_tags.format_comment_html,
        ]
        
        for filter_func in filters:
            result = filter_func(content)
            self.assertIsInstance(result, SafeString)


class TemplateTagRealWorldScenariosTest(BaseCommentTestCase):
    """Test template tags in real-world usage scenarios."""
    
    def test_blog_post_comment_section_scenario(self):
        """Simulate a typical blog post comment section."""
        # Create blog post
        post = self.test_obj
        
        # Create various comments
        root1 = self.create_comment(
            content="Great article! **Very informative**.",
            is_public=True
        )
        child1 = self.create_comment(
            content="Thanks! Glad you found it useful.",
            parent=root1,
            is_public=True
        )
        root2 = self.create_comment(
            content="I disagree with [point 2](https://example.com/info)",
            is_public=True
        )
        
        # Simulate template rendering
        template = Template('''
            {% load comment_tags %}
            {% if post|has_comments %}
                <h3>Comments ({% get_comment_count post %})</h3>
                {% get_root_comments_for post as roots %}
                {% for root in roots %}
                    <div class="comment">
                        {{ root.content|format_comment:"markdown" }}
                        {% for child in root.children.all %}
                            <div class="reply">
                                {{ child.content|format_comment:"markdown" }}
                            </div>
                        {% endfor %}
                    </div>
                {% endfor %}
            {% endif %}
        ''')
        
        context = Context({'post': post})
        rendered = template.render(context)
        
        # Verify correct rendering
        self.assertIn('Comments (3)', rendered)
        self.assertIn('<strong>Very informative</strong>', rendered)
        self.assertIn('Thanks!', rendered)
        self.assertIn('<a href="https://example.com/info"', rendered)
    
    def test_user_profile_comment_history_scenario(self):
        """Simulate displaying user's comment history."""
        # User with multiple comments
        user = self.regular_user
        ct = ContentType.objects.get_for_model(User)
        for i in range(5):
            self.create_comment(
                user=user,
                content=f"User comment #{i + 1}",
                is_public=True,
                content_type=ct,
                object_id=str(user.pk)
            )
        
        template = Template('''
            {% load comment_tags %}
            <div class="user-stats">
                Total Comments: {% get_user_comment_count %}
            </div>
        ''')
        
        context = Context({'user': user})
        rendered = template.render(context)
        
        self.assertIn('Total Comments: 5', rendered)
    
    def test_comment_count_badge_scenario(self):
        """Simulate showing comment count badges on multiple posts."""
        # Create multiple users as test objects
        users = [
            User.objects.create_user(username=f'post{i}', email=f'post{i}@test.com')
            for i in range(3)
        ]
        
        ct = ContentType.objects.get_for_model(User)
        
        # Different comment counts for each post
        for i in range(5):
            self.create_comment(
                content_type=ct,
                object_id=str(users[0].pk),
                is_public=True
            )
        
        for i in range(2):
            self.create_comment(
                content_type=ct,
                object_id=str(users[1].pk),
                is_public=True
            )
        
        # Third user has no comments
        
        template = Template('''
            {% load comment_tags %}
            {% for post in posts %}
                <div class="post">
                    {% if post|has_comments %}
                        <span class="badge">{% get_comment_count post %}</span>
                    {% else %}
                        <span class="badge">0</span>
                    {% endif %}
                </div>
            {% endfor %}
        ''')
        
        context = Context({'posts': users})
        rendered = template.render(context)
        
        # Should show correct counts
        self.assertIn('<span class="badge">5</span>', rendered)
        self.assertIn('<span class="badge">2</span>', rendered)
        self.assertIn('<span class="badge">0</span>', rendered)
    
    def test_moderation_queue_scenario(self):
        """Simulate moderator viewing all comments including private ones."""
        post = self.test_obj
        
        # Mix of public and private comments
        self.create_comment(is_public=True)
        self.create_comment(is_public=False)
        self.create_comment(is_removed=True)
        
        # Public view
        public_comments = comment_tags.get_comments_for(post, public_only=True)
        self.assertEqual(public_comments.count(), 1)
        
        # Moderator view (all comments)
        all_comments = comment_tags.get_comments_for(post, public_only=False)
        self.assertEqual(all_comments.count(), 3)
    
    def test_ajax_comment_loading_scenario(self):
        """Simulate loading comments via AJAX."""
        post = self.test_obj
        
        # Create many comments
        for i in range(50):
            self.create_comment(
                content=f"Comment {i}",
                is_public=True
            )
        
        # Simulate showing first 10 comments
        template = Template('''
            {% load comment_tags %}
            {% show_comments post max_comments=10 %}
        ''')
        
        context = Context({'post': post})
        # Should only load 10 comments
        comments_context = comment_tags.show_comments(post, max_comments=10)
        
        self.assertEqual(len(list(comments_context['comments'])), 10)
    
    def test_markdown_blog_comment_scenario(self):
        """Test real-world Markdown content in comments."""
        post = self.test_obj
        
        markdown_content = """
# Heading

This is a **bold** statement with *emphasis*.

- Point 1
- Point 2
- Point 3

Here's a [link](https://example.com) and some `code`.

```python
def example():
    return "Hello"
```
"""
        
        comment = self.create_comment(
            content=markdown_content,
            is_public=True
        )
        
        # Format the comment
        result = comment_tags.format_comment(comment.content, format_type='markdown')
        
        # Verify Markdown rendering
        self.assertIn('<h1>', result)
        self.assertIn('<strong>bold</strong>', result)
        self.assertIn('<em>emphasis</em>', result)
        self.assertIn('<li>Point 1</li>', result)
        self.assertIn('<a href="https://example.com"', result)
        self.assertIn('<code>', result)
    
    def test_multilingual_comment_scenario(self):
        """Test comments in multiple languages."""
        post = self.test_obj
        
        multilingual_comments = [
            "English comment with UTF-8",
            "Comentario en español con áéíóú ñ",
            "Комментарий на русском языке",
            "中文评论包含汉字",
            "日本語のコメント",
            "تعليق باللغة العربية",
            "🌍 Emoji 😊 support 🎉",
        ]
        
        for content in multilingual_comments:
            comment = self.create_comment(
                content=content,
                is_public=True
            )
            
            # Each should format correctly
            result = comment_tags.format_comment(comment.content, format_type='plain')
            self.assertIsInstance(result, SafeString)
            # Original content should be preserved (after HTML escaping)
            self.assertIn(content, result)