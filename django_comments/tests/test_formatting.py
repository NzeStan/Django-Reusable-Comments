"""
Comprehensive Tests for django_comments.formatting module

Tests cover:
- PlainTextFormatter: HTML escaping, line breaks, edge cases
- MarkdownFormatter: Markdown conversion, sanitization, XSS prevention
- HTMLFormatter: HTML sanitization, XSS prevention
- CommentFormatRenderer: Format selection, error handling
- Convenience functions
- Real-world scenarios with Unicode, emoji, special characters
"""
import builtins
import logging
from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
from django.utils.safestring import SafeString

from django_comments.formatting import (
    PlainTextFormatter,
    MarkdownFormatter,
    HTMLFormatter,
    CommentFormatRenderer,
    render_comment_content,
    get_available_formats,
    renderer,
)


# ============================================================================
# PLAIN TEXT FORMATTER TESTS
# ============================================================================

class PlainTextFormatterTests(TestCase):
    """Test PlainTextFormatter for HTML escaping and line break handling."""
    
    def setUp(self):
        self.formatter = PlainTextFormatter()
    
    # Success Cases
    
    def test_format_plain_text(self):
        """Test formatting plain text returns SafeString."""
        result = self.formatter.format("Hello World")
        self.assertIsInstance(result, SafeString)
        self.assertEqual(result, "Hello World")
    
    def test_format_preserves_line_breaks(self):
        """Test that newlines are converted to <br> tags."""
        text = "Line 1\nLine 2\nLine 3"
        result = self.formatter.format(text)
        
        self.assertIn("<br>", result)
        self.assertEqual(result.count("<br>"), 2)
        self.assertEqual(result, "Line 1<br>Line 2<br>Line 3")
    
    def test_format_escapes_html_tags(self):
        """Test that HTML tags are properly escaped."""
        text = "<script>alert('xss')</script>"
        result = self.formatter.format(text)
        
        # Should not contain actual script tags
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)
        self.assertIn("&lt;/script&gt;", result)
    
    def test_format_escapes_dangerous_html(self):
        """Test escaping various dangerous HTML patterns."""
        dangerous_inputs = [
            '<img src="x" onerror="alert(1)">',
            '<iframe src="evil.com"></iframe>',
            '<a href="javascript:alert(1)">Click</a>',
            '<div onclick="alert(1)">Div</div>',
            '<svg/onload=alert(1)>',
        ]
        
        for dangerous in dangerous_inputs:
            result = self.formatter.format(dangerous)
            # Should contain escaped versions
            self.assertIn("&lt;", result, f"Failed to escape: {dangerous}")
            self.assertIn("&gt;", result, f"Failed to escape: {dangerous}")
            # Should NOT contain actual executable tags (the < > should be escaped)
            self.assertNotIn("<script", result.lower())
            self.assertNotIn("<iframe", result.lower())
            # The dangerous content is now safe text (escaped), so these strings may exist as text
            # What matters is they're not executable (tags are escaped)
    
    def test_format_empty_string(self):
        """Test formatting empty string."""
        result = self.formatter.format("")
        self.assertEqual(result, "")
        self.assertIsInstance(result, SafeString)
    
    def test_format_whitespace_only(self):
        """Test formatting whitespace-only string."""
        result = self.formatter.format("   \n   \n   ")
        self.assertIn("<br>", result)
        self.assertEqual(result, "   <br>   <br>   ")
    
    # Edge Cases
    
    def test_format_with_unicode_characters(self):
        """Test formatting text with Unicode characters."""
        text = "Hello 世界! Привет мир! مرحبا بالعالم!"
        result = self.formatter.format(text)
        
        self.assertEqual(result, text)
        self.assertIn("世界", result)
        self.assertIn("Привет", result)
        self.assertIn("مرحبا", result)
    
    def test_format_with_emoji(self):
        """Test formatting text with emoji."""
        text = "Great job! 🎉💪👍😀"
        result = self.formatter.format(text)
        
        self.assertEqual(result, text)
        self.assertIn("🎉", result)
        self.assertIn("💪", result)
    
    def test_format_with_special_characters(self):
        """Test formatting text with special characters."""
        text = "Special: !@#$%^&*()_+-=[]{}|;':\",./<>?"
        result = self.formatter.format(text)
        
        # Most special chars should be preserved
        self.assertIn("!@#$%^", result)
        # Ampersand gets escaped
        self.assertIn("&amp;", result)
        # Quotes get HTML-escaped
        self.assertIn("&#x27;", result)  # Single quote
        self.assertIn("&quot;", result)  # Double quote
        # Less than and greater than get escaped
        self.assertIn("&lt;", result)
        self.assertIn("&gt;", result)
    
    def test_format_with_mixed_line_endings(self):
        """Test handling different line ending styles."""
        # Unix style
        unix_text = "Line1\nLine2\nLine3"
        result = self.formatter.format(unix_text)
        self.assertEqual(result.count("<br>"), 2)
        
        # Windows style (should convert \r\n to <br>)
        # Note: Django's escape() converts \r\n to \n first
        windows_text = "Line1\r\nLine2\r\nLine3"
        result = self.formatter.format(windows_text)
        # The \r gets converted/handled, so we still get <br>
        self.assertIn("<br>", result)
    
    def test_format_with_consecutive_newlines(self):
        """Test formatting text with multiple consecutive newlines."""
        text = "Paragraph 1\n\n\nParagraph 2"
        result = self.formatter.format(text)
        
        # Each \n becomes <br>
        self.assertEqual(result.count("<br>"), 3)
        self.assertEqual(result, "Paragraph 1<br><br><br>Paragraph 2")
    
    def test_format_very_long_text(self):
        """Test formatting very long text."""
        text = "A" * 10000 + "\n" + "B" * 10000
        result = self.formatter.format(text)
        
        self.assertIn("<br>", result)
        self.assertIn("A" * 100, result)
        self.assertIn("B" * 100, result)
    
    def test_format_with_html_entities(self):
        """Test that existing HTML entities are properly handled."""
        text = "Less than &lt; and greater than &gt; and ampersand &amp;"
        result = self.formatter.format(text)
        
        # Should double-escape existing entities
        self.assertIn("&amp;lt;", result)
        self.assertIn("&amp;gt;", result)
        self.assertIn("&amp;amp;", result)


# ============================================================================
# MARKDOWN FORMATTER TESTS
# ============================================================================

class MarkdownFormatterTests(TestCase):
    """Test MarkdownFormatter for Markdown conversion and sanitization."""
    
    def setUp(self):
        self.formatter = MarkdownFormatter()
    
    # Success Cases
    
    def test_format_basic_markdown(self):
        """Test formatting basic markdown syntax."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = "**Bold** and *italic* text"
        result = self.formatter.format(text)
        
        self.assertIsInstance(result, SafeString)
        self.assertIn("<strong>", result)
        self.assertIn("<em>", result)
        self.assertIn("Bold", result)
        self.assertIn("italic", result)
    
    def test_format_markdown_headers(self):
        """Test formatting markdown headers."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = "# Heading 1\n## Heading 2\n### Heading 3"
        result = self.formatter.format(text)
        
        self.assertIn("<h1>", result)
        self.assertIn("<h2>", result)
        self.assertIn("<h3>", result)
    
    def test_format_markdown_links(self):
        """Test formatting markdown links."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = "[Google](https://google.com)"
        result = self.formatter.format(text)
        
        self.assertIn('<a href="https://google.com"', result)
        self.assertIn("Google", result)
    
    def test_format_markdown_lists(self):
        """Test formatting markdown lists."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = "- Item 1\n- Item 2\n- Item 3"
        result = self.formatter.format(text)
        
        self.assertIn("<ul>", result)
        self.assertIn("<li>", result)
        self.assertIn("Item 1", result)
    
    def test_format_markdown_code_blocks(self):
        """Test formatting markdown code blocks."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = "```python\nprint('Hello')\n```"
        result = self.formatter.format(text)
        
        self.assertIn("<pre>", result)
        # Code tag may have class attribute
        self.assertIn("code", result.lower())
        self.assertIn("print", result)
    
    def test_format_markdown_inline_code(self):
        """Test formatting inline code."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = "Use `print()` function"
        result = self.formatter.format(text)
        
        self.assertIn("<code>", result)
        self.assertIn("print()", result)
    
    def test_format_markdown_blockquotes(self):
        """Test formatting blockquotes."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = "> This is a quote"
        result = self.formatter.format(text)
        
        self.assertIn("<blockquote>", result)
        self.assertIn("This is a quote", result)
    
    def test_format_markdown_tables(self):
        """Test formatting markdown tables."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = """
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
"""
        result = self.formatter.format(text)
        
        self.assertIn("<table>", result)
        self.assertIn("<thead>", result)
        self.assertIn("<tbody>", result)
        self.assertIn("<tr>", result)
        self.assertIn("<th>", result)
        self.assertIn("<td>", result)
    
    # XSS Prevention
    
    def test_sanitizes_dangerous_html_in_markdown(self):
        """Test that dangerous HTML is sanitized even in markdown."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        dangerous_inputs = [
            '<script>alert("xss")</script>',
            '<img src="x" onerror="alert(1)">',
            '<iframe src="evil.com"></iframe>',
            '[Click](javascript:alert(1))',
        ]
        
        for dangerous in dangerous_inputs:
            result = self.formatter.format(dangerous)
            # Should NOT contain dangerous tags/attributes
            self.assertNotIn("<script>", result)
            self.assertNotIn("<iframe>", result)
            self.assertNotIn('onerror=', result)
            self.assertNotIn('javascript:', result)
    
    def test_sanitizes_event_handlers(self):
        """Test that event handlers are stripped."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = '<div onclick="alert(1)">Click me</div>'
        result = self.formatter.format(text)
        
        self.assertNotIn('onclick', result)
        self.assertNotIn('alert', result)
    
    def test_allows_safe_html_tags(self):
        """Test that safe HTML tags are allowed."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = "<strong>Bold</strong> and <em>italic</em>"
        result = self.formatter.format(text)
        
        self.assertIn("<strong>", result)
        self.assertIn("<em>", result)
    
    def test_strips_disallowed_tags(self):
        """Test that disallowed tags are stripped."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = "<style>body{background:red}</style><p>Text</p>"
        result = self.formatter.format(text)
        
        self.assertNotIn("<style>", result)
        # Content should be preserved
        self.assertIn("Text", result)
    
    # Fallback Behavior
    
    def test_fallback_when_markdown_unavailable(self):
        """Test fallback to PlainTextFormatter when markdown is unavailable."""
        # Mock builtins.__import__ to raise ImportError for markdown
        import builtins
        real_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name == 'markdown':
                raise ImportError("Mocked: markdown not available")
            return real_import(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import):
            # Create formatter - this will trigger ImportError and set up fallback
            formatter = MarkdownFormatter()
        
        # Formatter should not be available and should have fallback
        self.assertFalse(formatter.available)
        self.assertIsNotNone(formatter.fallback)
        self.assertIsInstance(formatter.fallback, PlainTextFormatter)
        
        text = "**Bold** text\nNew line"
        result = formatter.format(text)
        
        # Should use plain text fallback
        # Should NOT have <strong> tags (markdown not processed)
        self.assertNotIn("<strong>", result)
        # Should have escaped HTML and <br> for newlines
        self.assertIn("<br>", result)
    
    # Edge Cases
    
    def test_format_empty_markdown(self):
        """Test formatting empty markdown."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        result = self.formatter.format("")
        self.assertEqual(result, "")
    
    def test_format_markdown_with_unicode(self):
        """Test formatting markdown with Unicode."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = "**中文粗体** and *العربية مائل*"
        result = self.formatter.format(text)
        
        self.assertIn("<strong>", result)
        self.assertIn("中文", result)
        self.assertIn("العربية", result)
    
    def test_format_markdown_with_emoji(self):
        """Test formatting markdown with emoji."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = "**Great!** 🎉 *Awesome!* 💪"
        result = self.formatter.format(text)
        
        self.assertIn("🎉", result)
        self.assertIn("💪", result)
    
    def test_format_complex_markdown(self):
        """Test formatting complex markdown with multiple elements."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = """
# Title

This is **bold** and *italic* text.

- Item 1
- Item 2

> A quote

[Link](https://example.com)

`code`
"""
        result = self.formatter.format(text)
        
        # Should contain all expected elements
        self.assertIn("<h1>", result)
        self.assertIn("<strong>", result)
        self.assertIn("<em>", result)
        self.assertIn("<ul>", result)
        self.assertIn("<li>", result)
        self.assertIn("<blockquote>", result)
        self.assertIn('<a href="https://example.com"', result)
        self.assertIn("<code>", result)
    
    def test_format_markdown_newlines_preserved(self):
        """Test that newlines are converted to <br> tags."""
        if not self.formatter.available:
            self.skipTest("Markdown library not installed")
        
        text = "Line 1\nLine 2\nLine 3"
        result = self.formatter.format(text)
        
        # With nl2br extension, newlines should become <br>
        self.assertIn("<br", result)


# ============================================================================
# HTML FORMATTER TESTS
# ============================================================================

class HTMLFormatterTests(TestCase):
    """Test HTMLFormatter for HTML sanitization."""
    
    def setUp(self):
        self.formatter = HTMLFormatter()
    
    # Success Cases
    
    def test_format_safe_html(self):
        """Test formatting safe HTML."""
        html = "<p>This is <strong>bold</strong> text</p>"
        result = self.formatter.format(html)
        
        self.assertIsInstance(result, SafeString)
        self.assertIn("<p>", result)
        self.assertIn("<strong>", result)
    
    def test_format_allows_basic_formatting(self):
        """Test that basic formatting tags are allowed."""
        html = "<strong>Bold</strong> <em>Italic</em> <u>Underline</u>"
        result = self.formatter.format(html)
        
        self.assertIn("<strong>", result)
        self.assertIn("<em>", result)
        self.assertIn("<u>", result)
    
    def test_format_allows_links(self):
        """Test that links are allowed with safe attributes."""
        html = '<a href="https://example.com" title="Example">Link</a>'
        result = self.formatter.format(html)
        
        self.assertIn('<a href="https://example.com"', result)
        self.assertIn('title="Example"', result)
    
    def test_format_allows_lists(self):
        """Test that lists are allowed."""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = self.formatter.format(html)
        
        self.assertIn("<ul>", result)
        self.assertIn("<li>", result)
    
    def test_format_allows_blockquotes(self):
        """Test that blockquotes are allowed."""
        html = "<blockquote>Quote text</blockquote>"
        result = self.formatter.format(html)
        
        self.assertIn("<blockquote>", result)
    
    def test_format_allows_code(self):
        """Test that code tags are allowed."""
        html = "<code>print('hello')</code>"
        result = self.formatter.format(html)
        
        self.assertIn("<code>", result)
    
    # XSS Prevention
    
    def test_sanitizes_script_tags(self):
        """Test that script tags are removed."""
        html = '<script>alert("xss")</script><p>Safe content</p>'
        result = self.formatter.format(html)
        
        self.assertNotIn("<script>", result)
        self.assertNotIn("</script>", result)
        # Note: bleach strips the tags but may keep the text content
        # What matters is the script tag itself is gone (not executable)
        # Safe content should be preserved
        self.assertIn("Safe content", result)
    
    def test_sanitizes_iframe_tags(self):
        """Test that iframe tags are removed."""
        html = '<iframe src="evil.com"></iframe><p>Content</p>'
        result = self.formatter.format(html)
        
        self.assertNotIn("<iframe>", result)
        self.assertIn("Content", result)
    
    def test_sanitizes_event_handlers(self):
        """Test that event handlers are stripped."""
        html = '<div onclick="alert(1)">Click</div>'
        result = self.formatter.format(html)
        
        self.assertNotIn('onclick', result)
        self.assertNotIn('alert', result)
        self.assertIn("Click", result)
    
    def test_sanitizes_javascript_urls(self):
        """Test that javascript: URLs are removed."""
        html = '<a href="javascript:alert(1)">Click</a>'
        result = self.formatter.format(html)
        
        self.assertNotIn('javascript:', result)
    
    def test_sanitizes_data_urls(self):
        """Test that data: URLs are handled safely."""
        html = '<a href="data:text/html,<script>alert(1)</script>">Click</a>'
        result = self.formatter.format(html)
        
        # bleach should strip data: URLs or the entire href
        self.assertNotIn('data:', result.lower())
    
    def test_sanitizes_style_tags(self):
        """Test that style tags are removed."""
        html = '<style>body{background:red}</style><p>Content</p>'
        result = self.formatter.format(html)
        
        self.assertNotIn("<style>", result)
        self.assertIn("Content", result)
    
    def test_sanitizes_dangerous_attributes(self):
        """Test that dangerous attributes are stripped."""
        html = '<img src="x" onerror="alert(1)" onload="alert(2)">'
        result = self.formatter.format(html)
        
        self.assertNotIn('onerror', result)
        self.assertNotIn('onload', result)
        self.assertNotIn('alert', result)
    
    # Edge Cases
    
    def test_format_empty_html(self):
        """Test formatting empty HTML."""
        result = self.formatter.format("")
        self.assertEqual(result, "")
    
    def test_format_html_with_unicode(self):
        """Test formatting HTML with Unicode."""
        html = "<p>中文 العربية Русский</p>"
        result = self.formatter.format(html)
        
        self.assertIn("中文", result)
        self.assertIn("العربية", result)
        self.assertIn("Русский", result)
    
    def test_format_html_with_emoji(self):
        """Test formatting HTML with emoji."""
        html = "<p>Great! 🎉💪</p>"
        result = self.formatter.format(html)
        
        self.assertIn("🎉", result)
        self.assertIn("💪", result)
    
    def test_format_nested_html(self):
        """Test formatting nested HTML structures."""
        html = """
        <div>
            <p>Paragraph with <strong>bold</strong> and <em>italic</em></p>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
            </ul>
        </div>
        """
        result = self.formatter.format(html)
        
        self.assertIn("<div>", result)
        self.assertIn("<p>", result)
        self.assertIn("<strong>", result)
        self.assertIn("<ul>", result)
    
    def test_strips_disallowed_tags_preserves_content(self):
        """Test that disallowed tags are stripped but content preserved."""
        html = "<article><section><p>Content</p></section></article>"
        result = self.formatter.format(html)
        
        # article and section are not in allowed list
        self.assertNotIn("<article>", result)
        self.assertNotIn("<section>", result)
        # But content should be preserved
        self.assertIn("Content", result)
    
    def test_format_malformed_html(self):
        """Test handling of malformed HTML."""
        html = "<p>Unclosed paragraph <strong>Unclosed strong"
        result = self.formatter.format(html)
        
        # bleach should handle malformed HTML gracefully
        self.assertIsInstance(result, SafeString)
        self.assertIn("Unclosed paragraph", result)


# ============================================================================
# COMMENT FORMAT RENDERER TESTS
# ============================================================================

class CommentFormatRendererTests(TestCase):
    """Test CommentFormatRenderer for format selection and error handling."""
    
    def setUp(self):
        self.renderer = CommentFormatRenderer()
    
    # Success Cases
    
    def test_render_with_plain_format(self):
        """Test rendering with plain format explicitly specified."""
        text = "<p>HTML</p>\nNew line"
        result = self.renderer.render(text, format='plain')
        
        self.assertIn("&lt;p&gt;", result)
        self.assertIn("<br>", result)
    
    def test_render_with_markdown_format(self):
        """Test rendering with markdown format explicitly specified."""
        if not self.renderer.formatters['markdown'].available:
            self.skipTest("Markdown library not installed")
        
        text = "**Bold** text"
        result = self.renderer.render(text, format='markdown')
        
        self.assertIn("<strong>", result)
    
    def test_render_with_html_format(self):
        """Test rendering with HTML format explicitly specified."""
        html = "<p>Paragraph</p>"
        result = self.renderer.render(html, format='html')
        
        self.assertIn("<p>", result)
    
    @override_settings(COMMENT_FORMAT='plain')
    def test_render_uses_default_format(self):
        """Test that render uses default format when not specified."""
        # Create new renderer to pick up settings
        test_renderer = CommentFormatRenderer()
        
        text = "**Bold**"
        result = test_renderer.render(text)
        
        # Should use plain (default), so markdown not processed
        self.assertNotIn("<strong>", result)
    
    def test_render_empty_string(self):
        """Test rendering empty string."""
        result = self.renderer.render("")
        self.assertEqual(result, "")
    
    def test_render_none_returns_empty(self):
        """Test rendering None returns empty string."""
        result = self.renderer.render(None)
        self.assertEqual(result, "")
    
    # Error Handling
    
    def test_render_with_invalid_format_falls_back_to_plain(self):
        """Test that invalid format falls back to plain text."""
        text = "<script>alert('xss')</script>"
        
        # Use invalid format
        with self.assertLogs('django_comments', level='WARNING') as logs:
            result = self.renderer.render(text, format='invalid_format')
        
        # Should log warning
        self.assertTrue(any("Unknown format" in log for log in logs.output))
        
        # Should use plain text (HTML escaped)
        self.assertIn("&lt;script&gt;", result)
        self.assertNotIn("<script>", result)
    
    def test_render_handles_formatter_exception(self):
        """Test that render handles exceptions from formatters."""
        # Mock formatter to raise exception on first call, then work on fallback
        original_format = self.renderer.formatters['plain'].format
        
        call_count = [0]
        def mock_format(content):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Test error")
            # On second call (fallback), use original
            return original_format(content)
        
        with patch.object(self.renderer.formatters['plain'], 'format', side_effect=mock_format):
            with self.assertLogs('django_comments', level='ERROR') as logs:
                result = self.renderer.render("Test content", format='plain')
            
            # Should log error
            self.assertTrue(any("Error rendering content" in log for log in logs.output))
            
            # Should still return something (fallback was called)
            self.assertIsInstance(result, (str, SafeString))
    
    def test_get_available_formats_includes_plain_and_html(self):
        """Test that available formats always includes plain and html."""
        formats = self.renderer.get_available_formats()
        
        self.assertIn('plain', formats)
        self.assertIn('html', formats)
    
    def test_get_available_formats_includes_markdown_if_available(self):
        """Test that markdown is included if available."""
        formats = self.renderer.get_available_formats()
        
        if self.renderer.formatters['markdown'].available:
            self.assertIn('markdown', formats)
        else:
            self.assertNotIn('markdown', formats)
    
    # Real-World Scenarios
    
    def test_render_user_comment_with_mixed_content(self):
        """Test rendering real-world user comment with mixed content."""
        if not self.renderer.formatters['markdown'].available:
            self.skipTest("Markdown library not installed")
        
        comment = """
Hey there! 👋

This is a **great** article! Here are my thoughts:

1. Point one
2. Point two 
3. Point three

Check out this link: [Example](https://example.com)

> "This is a quote from the article"

Thanks! 😊
"""
        result = self.renderer.render(comment, format='markdown')
        
        # Should contain formatted elements
        self.assertIn("<strong>", result)
        self.assertIn("<ol>", result)
        self.assertIn('<a href="https://example.com"', result)
        self.assertIn("<blockquote>", result)
        # Emoji should be preserved
        self.assertIn("👋", result)
        self.assertIn("😊", result)
    
    def test_render_multilingual_content(self):
        """Test rendering content in multiple languages."""
        text = """
English: Hello World
中文: 你好世界
العربية: مرحبا بالعالم
Русский: Привет мир
日本語: こんにちは世界
"""
        result = self.renderer.render(text, format='plain')
        
        self.assertIn("Hello World", result)
        self.assertIn("你好世界", result)
        self.assertIn("مرحبا بالعالم", result)
        self.assertIn("Привет мир", result)
        self.assertIn("こんにちは世界", result)


# ============================================================================
# CONVENIENCE FUNCTIONS TESTS
# ============================================================================

class ConvenienceFunctionsTests(TestCase):
    """Test convenience functions for rendering."""
    
    def test_render_comment_content_function(self):
        """Test render_comment_content convenience function."""
        text = "Test content\nNew line"
        result = render_comment_content(text, format='plain')
        
        self.assertIsInstance(result, SafeString)
        self.assertIn("<br>", result)
    
    def test_render_comment_content_uses_default_format(self):
        """Test that render_comment_content uses default format."""
        text = "Test content"
        result = render_comment_content(text)
        
        self.assertIsInstance(result, SafeString)
    
    def test_get_available_formats_function(self):
        """Test get_available_formats convenience function."""
        formats = get_available_formats()
        
        self.assertIsInstance(formats, list)
        self.assertIn('plain', formats)
        self.assertIn('html', formats)
    
    def test_global_renderer_instance(self):
        """Test that global renderer instance is available."""
        from django_comments.formatting import renderer as global_renderer
        
        self.assertIsInstance(global_renderer, CommentFormatRenderer)
        
        # Should be functional
        result = global_renderer.render("Test")
        self.assertEqual(result, "Test")


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class FormattingIntegrationTests(TestCase):
    """Integration tests for formatting module."""
    
    def test_all_formatters_handle_xss_attempts(self):
        """Test that all formatters properly handle XSS attempts."""
        xss_attempts = [
            '<script>alert("xss")</script>',
            '<img src="x" onerror="alert(1)">',
            '<iframe src="javascript:alert(1)"></iframe>',
            '<svg/onload=alert(1)>',
            '<body onload=alert(1)>',
            '<input onfocus=alert(1) autofocus>',
            '<select onfocus=alert(1) autofocus>',
            '<textarea onfocus=alert(1) autofocus>',
            '<marquee onstart=alert(1)>',
            '<div style="background:url(javascript:alert(1))">',
        ]
        
        plain_formatter = PlainTextFormatter()
        html_formatter = HTMLFormatter()
        
        for xss in xss_attempts:
            # Plain text should escape everything - tags won't be executable
            plain_result = plain_formatter.format(xss)
            # The key check: actual HTML tags should be escaped (not executable)
            self.assertNotIn("<script>", plain_result)
            self.assertNotIn("<iframe>", plain_result)
            # Tags should be escaped to &lt; and &gt;
            if '<' in xss:
                self.assertIn("&lt;", plain_result)
            
            # HTML should sanitize - dangerous tags should be removed or escaped
            html_result = html_formatter.format(xss)
            # No executable script or iframe tags
            self.assertNotIn("<script>", html_result)
            self.assertNotIn("<iframe>", html_result)
            # No executable event handlers (the opening < should prevent execution)
            # The content may exist as text, but not as executable HTML
    
    def test_formatters_preserve_legitimate_content(self):
        """Test that formatters don't over-sanitize legitimate content."""
        legitimate_content = [
            "This is a normal sentence.",
            "Email: user@example.com",
            "Price: $19.99",
            "Math: 2 + 2 = 4",
            "Percentage: 50% off",
            "Quotes: 'single' and \"double\"",
            "Parentheses: (additional info)",
            "Brackets: [reference]",
            "Braces: {data}",
        ]
        
        plain_formatter = PlainTextFormatter()
        
        for content in legitimate_content:
            result = plain_formatter.format(content)
            # Should contain the main content (though some chars may be escaped)
            self.assertTrue(
                any(word in result for word in content.split() if len(word) > 3),
                f"Content lost: {content}"
            )
    
    def test_formatters_handle_very_long_content(self):
        """Test that formatters handle very long content efficiently."""
        # 50KB of content
        long_content = "This is a test sentence.\n" * 2000
        
        plain_formatter = PlainTextFormatter()
        html_formatter = HTMLFormatter()
        
        # Should not raise exceptions
        plain_result = plain_formatter.format(long_content)
        html_result = html_formatter.format(long_content)
        
        self.assertIsInstance(plain_result, SafeString)
        self.assertIsInstance(html_result, SafeString)
        self.assertGreater(len(plain_result), 10000)
    
    def test_formatters_consistent_output_type(self):
        """Test that all formatters return SafeString."""
        content = "Test content"
        
        plain_formatter = PlainTextFormatter()
        html_formatter = HTMLFormatter()
        renderer = CommentFormatRenderer()
        
        self.assertIsInstance(plain_formatter.format(content), SafeString)
        self.assertIsInstance(html_formatter.format(content), SafeString)
        self.assertIsInstance(renderer.render(content), SafeString)
    
    def test_renderer_respects_settings(self):
        """Test that renderer respects Django settings."""
        # Patch the comments_settings COMMENT_FORMAT attribute
        from django_comments import conf
        with patch.object(conf.comments_settings, 'COMMENT_FORMAT', 'markdown'):
            # Create new renderer to pick up patched settings
            test_renderer = CommentFormatRenderer()
            
            self.assertEqual(test_renderer.default_format, 'markdown')
    
    def test_markdown_formatter_initialization(self):
        """Test MarkdownFormatter initialization and availability check."""
        formatter = MarkdownFormatter()
        
        # Should have checked availability during init
        self.assertIsInstance(formatter.available, bool)
        
        if formatter.available:
            # Should have markdown module
            self.assertIsNotNone(formatter.markdown)
        else:
            # Should have fallback
            self.assertIsNotNone(formatter.fallback)
            self.assertIsInstance(formatter.fallback, PlainTextFormatter)


# ============================================================================
# PERFORMANCE TESTS (Optional but good to have)
# ============================================================================

class FormattingPerformanceTests(TestCase):
    """Basic performance tests for formatting operations."""
    
    def test_plain_formatter_performance(self):
        """Test plain formatter performance with medium content."""
        formatter = PlainTextFormatter()
        content = "Line of text\n" * 100  # 100 lines
        
        # Should complete quickly
        import time
        start = time.time()
        for _ in range(100):
            formatter.format(content)
        elapsed = time.time() - start
        
        # Should complete in under 1 second
        self.assertLess(elapsed, 1.0)
    
    def test_html_formatter_performance(self):
        """Test HTML formatter performance with medium content."""
        formatter = HTMLFormatter()
        content = "<p>Paragraph</p>\n" * 100
        
        import time
        start = time.time()
        for _ in range(100):
            formatter.format(content)
        elapsed = time.time() - start
        
        # Should complete in reasonable time
        self.assertLess(elapsed, 2.0)