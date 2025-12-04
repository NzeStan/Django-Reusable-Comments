"""
Comprehensive test suite for content formatting system.
Tests plain text, markdown, and HTML formatting with XSS protection.
"""
import pytest
from django_comments.formatting import (
    render_comment_content,
    get_available_formats,
    PlainTextFormatter,
    MarkdownFormatter,
    HTMLFormatter,
    CommentFormatRenderer,
)

pytestmark = pytest.mark.django_db


class TestPlainTextFormatter:
    """Tests for plain text formatting."""
    
    def test_plain_text_escapes_html(self):
        """Test that HTML is escaped in plain text."""
        formatter = PlainTextFormatter()
        content = '<script>alert("xss")</script>'
        result = formatter.format(content)
        
        assert '<script>' not in result
        assert '&lt;script&gt;' in result
    
    def test_plain_text_preserves_line_breaks(self):
        """Test that line breaks are converted to <br>."""
        formatter = PlainTextFormatter()
        content = "Line 1\nLine 2\nLine 3"
        result = formatter.format(content)
        
        assert '<br>' in result
        assert result.count('<br>') == 2
    
    def test_plain_text_escapes_special_chars(self):
        """Test that special HTML characters are escaped."""
        formatter = PlainTextFormatter()
        content = '< > & " \''
        result = formatter.format(content)
        
        assert '&lt;' in result
        assert '&gt;' in result
        assert '&amp;' in result
    
    def test_plain_text_handles_empty_content(self):
        """Test handling of empty content."""
        formatter = PlainTextFormatter()
        result = formatter.format("")
        
        assert result == ""
    
    def test_plain_text_handles_unicode(self):
        """Test handling of unicode content."""
        formatter = PlainTextFormatter()
        content = "Hello 世界 🌍"
        result = formatter.format(content)
        
        assert "Hello" in result
        assert "世界" in result
        assert "🌍" in result


class TestMarkdownFormatter:
    """Tests for markdown formatting."""
    
    def test_markdown_bold(self):
        """Test markdown bold formatting."""
        formatter = MarkdownFormatter()
        if not formatter.available:
            pytest.skip("Markdown not available")
        
        content = "**Bold text**"
        result = formatter.format(content)
        
        assert '<strong>Bold text</strong>' in result
    
    def test_markdown_italic(self):
        """Test markdown italic formatting."""
        formatter = MarkdownFormatter()
        if not formatter.available:
            pytest.skip("Markdown not available")
        
        content = "*Italic text*"
        result = formatter.format(content)
        
        assert '<em>Italic text</em>' in result
    
    def test_markdown_links(self):
        """Test markdown links."""
        formatter = MarkdownFormatter()
        if not formatter.available:
            pytest.skip("Markdown not available")
        
        content = "[Link text](https://example.com)"
        result = formatter.format(content)
        
        assert '<a href="https://example.com">Link text</a>' in result or '<a ' in result
    
    def test_markdown_code_blocks(self):
        """Test markdown code blocks."""
        formatter = MarkdownFormatter()
        if not formatter.available:
            pytest.skip("Markdown not available")
        
        content = "```\ncode here\n```"
        result = formatter.format(content)
        
        assert '<code>' in result or '<pre>' in result
    
    def test_markdown_sanitizes_dangerous_html(self):
        """Test that markdown sanitizes dangerous HTML."""
        formatter = MarkdownFormatter()
        if not formatter.available:
            pytest.skip("Markdown not available")
        
        content = '<script>alert("xss")</script>'
        result = formatter.format(content)
        
        # Should not contain script tag
        assert '<script>' not in result.lower()
    
    def test_markdown_allows_safe_html(self):
        """Test that markdown allows safe HTML tags."""
        formatter = MarkdownFormatter()
        if not formatter.available:
            pytest.skip("Markdown not available")
        
        content = "**Bold** and <strong>also bold</strong>"
        result = formatter.format(content)
        
        assert '<strong>' in result
    
    def test_markdown_fallback_to_plain_text(self):
        """Test fallback when markdown unavailable."""
        formatter = MarkdownFormatter()
        
        # Simulate markdown not available
        original_available = formatter.available
        formatter.available = False
        
        content = "**Bold**"
        result = formatter.format(content)
        
        # Should fall back to plain text
        assert '**Bold**' in result or '&' in result
        
        formatter.available = original_available
    
    def test_markdown_line_breaks(self):
        """Test markdown line break handling."""
        formatter = MarkdownFormatter()
        if not formatter.available:
            pytest.skip("Markdown not available")
        
        content = "Line 1\nLine 2"
        result = formatter.format(content)
        
        # Should have line breaks
        assert '<br' in result or '<p>' in result


class TestHTMLFormatter:
    """Tests for HTML formatting."""
    
    def test_html_allows_safe_tags(self):
        """Test that safe HTML tags are allowed."""
        formatter = HTMLFormatter()
        content = '<p>Paragraph</p><strong>Bold</strong><em>Italic</em>'
        result = formatter.format(content)
        
        assert '<p>Paragraph</p>' in result
        assert '<strong>Bold</strong>' in result
        assert '<em>Italic</em>' in result
    
    def test_html_removes_script_tags(self):
        """Test that script tags are removed."""
        formatter = HTMLFormatter()
        content = '<script>alert("xss")</script><p>Safe content</p>'
        result = formatter.format(content)
        
        assert '<script>' not in result
        assert '<p>Safe content</p>' in result
    
    def test_html_removes_event_handlers(self):
        """Test that event handlers are removed."""
        formatter = HTMLFormatter()
        content = '<a href="#" onclick="alert(\'xss\')">Link</a>'
        result = formatter.format(content)
        
        assert 'onclick' not in result.lower()
        assert '<a' in result
    
    def test_html_allows_links(self):
        """Test that links are allowed."""
        formatter = HTMLFormatter()
        content = '<a href="https://example.com">Link</a>'
        result = formatter.format(content)
        
        assert '<a href="https://example.com">Link</a>' in result
    
    def test_html_removes_style_tags(self):
        """Test that style tags are removed."""
        formatter = HTMLFormatter()
        content = '<style>body { display: none; }</style><p>Content</p>'
        result = formatter.format(content)
        
        assert '<style>' not in result
        assert '<p>Content</p>' in result
    
    def test_html_handles_nested_tags(self):
        """Test handling of nested tags."""
        formatter = HTMLFormatter()
        content = '<p><strong>Bold <em>and italic</em></strong></p>'
        result = formatter.format(content)
        
        assert '<strong>' in result
        assert '<em>' in result


class TestCommentFormatRenderer:
    """Tests for main renderer class."""
    
    def test_renderer_uses_default_format(self, settings):
        """Test renderer uses default format from settings."""
        settings.DJANGO_COMMENTS_CONFIG = {
            'COMMENT_FORMAT': 'plain',
        }
        from django_comments import conf
        conf.comments_settings = conf.CommentsSettings(
            settings.DJANGO_COMMENTS_CONFIG,
            conf.DEFAULTS
        )
        
        renderer = CommentFormatRenderer()
        content = "**Bold**"
        result = renderer.render(content)
        
        # Should use plain text (not render markdown)
        assert '**' in result or '&' in result
    
    def test_renderer_explicit_format_override(self):
        """Test explicit format overrides default."""
        renderer = CommentFormatRenderer()
        content = "Test"
        
        # Force plain text
        result = renderer.render(content, format='plain')
        assert 'Test' in result
    
    def test_renderer_unknown_format_falls_back(self):
        """Test unknown format falls back to plain text."""
        renderer = CommentFormatRenderer()
        content = "<p>Test</p>"
        
        result = renderer.render(content, format='unknown_format')
        
        # Should fall back to plain text
        assert '&lt;p&gt;' in result or '<p>' not in result
    
    def test_renderer_handles_empty_content(self):
        """Test handling of empty content."""
        renderer = CommentFormatRenderer()
        result = renderer.render("")
        
        assert result == ""
    
    def test_renderer_get_available_formats(self):
        """Test getting available formats."""
        renderer = CommentFormatRenderer()
        formats = renderer.get_available_formats()
        
        assert 'plain' in formats
        assert 'html' in formats
        # Markdown may or may not be available


class TestRenderCommentContentFunction:
    """Tests for render_comment_content convenience function."""
    
    def test_render_with_default_format(self):
        """Test rendering with default format."""
        content = "Test content"
        result = render_comment_content(content)
        
        assert 'Test content' in result
    
    def test_render_with_explicit_format(self):
        """Test rendering with explicit format."""
        content = "**Bold**"
        result_plain = render_comment_content(content, format='plain')
        
        assert '**' in result_plain or '&' in result_plain
    
    def test_render_handles_none_content(self):
        """Test handling of None content."""
        result = render_comment_content(None)
        assert result == ""


class TestGetAvailableFormatsFunction:
    """Tests for get_available_formats function."""
    
    def test_get_available_formats(self):
        """Test getting list of available formats."""
        formats = get_available_formats()
        
        assert isinstance(formats, list)
        assert 'plain' in formats
        assert 'html' in formats


class TestXSSProtection:
    """Tests for XSS protection across all formatters."""
    
    XSS_VECTORS = [
        '<script>alert("xss")</script>',
        '<img src=x onerror="alert(\'xss\')">',
        '<a href="javascript:alert(\'xss\')">Click</a>',
        '<iframe src="evil.com"></iframe>',
        '<object data="evil.swf"></object>',
        '<embed src="evil.swf">',
        '<style>body{display:none}</style>',
        '<link rel="stylesheet" href="evil.css">',
        '<base href="evil.com">',
        '<meta http-equiv="refresh" content="0;url=evil.com">',
    ]
    
    @pytest.mark.parametrize("xss_vector", XSS_VECTORS)
    def test_plain_text_blocks_xss(self, xss_vector):
        """Test plain text formatter blocks XSS vectors."""
        formatter = PlainTextFormatter()
        result = formatter.format(xss_vector)
        
        # Should escape HTML
        assert '<' not in result or '&lt;' in result
    
    @pytest.mark.parametrize("xss_vector", XSS_VECTORS)
    def test_html_formatter_blocks_xss(self, xss_vector):
        """Test HTML formatter blocks XSS vectors."""
        formatter = HTMLFormatter()
        result = formatter.format(xss_vector)
        
        # Should remove dangerous tags/attributes
        dangerous_patterns = [
            '<script',
            'javascript:',
            'onerror=',
            'onclick=',
            '<iframe',
            '<object',
            '<embed',
            '<style',
        ]
        
        result_lower = result.lower()
        for pattern in dangerous_patterns:
            assert pattern not in result_lower


class TestPerformance:
    """Tests for formatting performance."""
    
    def test_plain_text_performance(self):
        """Test plain text formatter performance."""
        formatter = PlainTextFormatter()
        content = "Test content\n" * 1000  # Long content
        
        import time
        start = time.time()
        result = formatter.format(content)
        elapsed = time.time() - start
        
        assert elapsed < 0.1  # Should be fast
        assert 'Test content' in result
    
    def test_markdown_performance(self):
        """Test markdown formatter performance."""
        formatter = MarkdownFormatter()
        if not formatter.available:
            pytest.skip("Markdown not available")
        
        content = "**Bold** *italic*\n" * 100
        
        import time
        start = time.time()
        result = formatter.format(content)
        elapsed = time.time() - start
        
        assert elapsed < 1.0  # Should complete in reasonable time


class TestEdgeCases:
    """Tests for edge cases and special characters."""
    
    def test_unicode_handling(self):
        """Test unicode character handling."""
        content = "Hello 世界 🌍 مرحبا"
        
        for format_type in ['plain', 'html']:
            result = render_comment_content(content, format=format_type)
            assert "Hello" in result
    
    def test_very_long_content(self):
        """Test handling of very long content."""
        content = "A" * 10000
        result = render_comment_content(content, format='plain')
        
        assert "A" in result
    
    def test_special_markdown_chars_in_plain_text(self):
        """Test markdown special chars in plain text mode."""
        content = "**Bold** _italic_ `code` # Header"
        result = render_comment_content(content, format='plain')
        
        # Should preserve literal characters
        assert '**' in result or '&' in result
    
    def test_null_bytes(self):
        """Test handling of null bytes."""
        content = "Test\x00content"
        result = render_comment_content(content, format='plain')
        
        # Should handle gracefully
        assert isinstance(result, str)


class TestIntegrationWithCommentModel:
    """Tests for integration with Comment model."""
    
    @pytest.mark.django_db
    def test_formatted_content_in_serializer(self, settings):
        """Test formatted content in serializer."""
        from django_comments.models import Comment
        from django_comments.api.serializers import CommentSerializer
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user('test', 'test@example.com', 'pass')
        
        # Create comment with markdown-style content
        comment = Comment(
            user=user,
            content="**Bold** text",
            content_type_id=1,
            object_id="1"
        )
        comment.save()
        
        # Serialize
        serializer = CommentSerializer(comment)
        
        # Should have formatted_content field if added to serializer
        if 'formatted_content' in serializer.fields:
            formatted = serializer.data.get('formatted_content', '')
            assert formatted  # Should be formatted


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v'])