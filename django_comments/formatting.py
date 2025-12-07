import logging
import bleach
from django.utils.safestring import mark_safe
from django.utils.html import escape
from .conf import comments_settings

logger = logging.getLogger(comments_settings.LOGGER_NAME)


class CommentFormatter:
    """Base class for comment content formatters."""
    
    def format(self, content: str) -> str:
        """
        Format comment content.
        
        Args:
            content: Raw comment content
        
        Returns:
            Formatted content (safe for display)
        """
        raise NotImplementedError


class PlainTextFormatter(CommentFormatter):
    """
    Plain text formatter.
    Escapes HTML and preserves line breaks.
    """
    
    def format(self, content: str) -> str:
        """Format as plain text with HTML escaped."""
        # Escape HTML
        content = escape(content)
        
        # Convert line breaks to <br>
        content = content.replace('\n', '<br>')
        
        return mark_safe(content)


class MarkdownFormatter(CommentFormatter):
    """
    Markdown formatter.
    Converts markdown to HTML with sanitization.
    """
    
    def __init__(self):
        # Try to import markdown
        try:
            import markdown
            self.markdown = markdown
            self.available = True
        except ImportError:
            logger.warning(
                "markdown library not installed. "
                "Install with: pip install markdown"
            )
            self.available = False
            # Fallback to plain text
            self.fallback = PlainTextFormatter()
    
    def format(self, content: str) -> str:
        """Format as markdown."""
        if not self.available:
            logger.debug("Markdown not available, using plain text fallback")
            return self.fallback.format(content)
        
        # Convert markdown to HTML
        html = self.markdown.markdown(
            content,
            extensions=[
                'markdown.extensions.nl2br',  # Convert newlines to <br>
                'markdown.extensions.fenced_code',  # Support code blocks
                'markdown.extensions.tables',  # Support tables
            ]
        )
        
        # Sanitize HTML
        html = self._sanitize_html(html)
        
        return mark_safe(html)
    
    def _sanitize_html(self, html: str) -> str:
        """Sanitize HTML to prevent XSS."""
        # Allowed tags
        allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li',
            'blockquote', 'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'table', 'thead', 'tbody', 'tr', 'th', 'td',
        ]
        
        # Allowed attributes
        allowed_attributes = {
            'a': ['href', 'title', 'rel'],
            'code': ['class'],
            'pre': ['class'],
        }
        
        # Clean HTML
        clean_html = bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )
        
        return clean_html


class HTMLFormatter(CommentFormatter):
    """
    HTML formatter.
    Allows safe HTML with strict sanitization.
    """
    
    def format(self, content: str) -> str:
        """Format as HTML with sanitization."""
        # Sanitize HTML
        html = self._sanitize_html(content)
        
        return mark_safe(html)
    
    def _sanitize_html(self, html: str) -> str:
        """Sanitize HTML to prevent XSS."""
        # Allowed tags (more restrictive than markdown)
        allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li',
            'blockquote', 'code', 'span', 'div',
        ]
        
        # Allowed attributes
        allowed_attributes = {
            'a': ['href', 'title', 'rel'],
            'span': ['class'],
            'div': ['class'],
        }
        
        # Clean HTML
        clean_html = bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )
        
        return clean_html


class CommentFormatRenderer:
    """
    Main renderer for comment content.
    Handles format detection and rendering.
    """
    
    def __init__(self):
        self.formatters = {
            'plain': PlainTextFormatter(),
            'markdown': MarkdownFormatter(),
            'html': HTMLFormatter(),
        }
        self.default_format = comments_settings.COMMENT_FORMAT
    
    def render(self, content: str, format: str = None) -> str:
        """
        Render comment content with specified format.
        
        Args:
            content: Raw comment content
            format: Format to use ('plain', 'markdown', 'html')
                   If None, uses COMMENT_FORMAT setting
        
        Returns:
            Formatted content safe for display
        """
        if not content:
            return ''
        
        # Use default format if not specified
        if format is None:
            format = self.default_format
        
        # Get formatter
        formatter = self.formatters.get(format)
        
        if not formatter:
            logger.warning(f"Unknown format '{format}', using plain text")
            formatter = self.formatters['plain']
        
        # Render content
        try:
            return formatter.format(content)
        except Exception as e:
            logger.error(f"Error rendering content with format '{format}': {e}")
            # Fallback to plain text
            return self.formatters['plain'].format(content)
    
    def get_available_formats(self) -> list:
        """Get list of available formats."""
        formats = ['plain', 'html']
        
        # Check if markdown is available
        if self.formatters['markdown'].available:
            formats.append('markdown')
        
        return formats


# Global renderer instance
renderer = CommentFormatRenderer()


# Convenience function
def render_comment_content(content: str, format: str = None) -> str:
    """
    Render comment content.
    
    Args:
        content: Raw comment content
        format: Format to use (optional)
    
    Returns:
        Formatted content safe for display
    
    Example:
        >>> from django_comments.formatting import render_comment_content
        >>> html = render_comment_content("**Bold** text", format='markdown')
        >>> print(html)
        <p><strong>Bold</strong> text</p>
    """
    return renderer.render(content, format)


def get_available_formats() -> list:
    """
    Get list of available comment formats.
    
    Returns:
        List of format names
    
    Example:
        >>> from django_comments.formatting import get_available_formats
        >>> formats = get_available_formats()
        >>> print(formats)
        ['plain', 'markdown', 'html']
    """
    return renderer.get_available_formats()