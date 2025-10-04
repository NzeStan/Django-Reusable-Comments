class CommentsError(Exception):
    """Base exception for all django-comments errors."""
    pass


class CommentDisallowed(CommentsError):
    """
    Exception raised when a comment is not allowed.
    This could be due to spam, content restrictions, etc.
    """
    pass


class CommentingDisabled(CommentsError):
    """
    Exception raised when commenting is disabled for a model or instance.
    """
    pass


class ContentTypeInvalid(CommentsError):
    """
    Exception raised when an invalid content type is specified.
    """
    pass


class ObjectDoesNotExist(CommentsError):
    """
    Exception raised when the commented object does not exist.
    """
    pass


class CommentModerated(CommentsError):
    """
    Not a true error, but raised when a comment is successfully submitted
    but requires moderation before being displayed.
    """
    def __init__(self, comment=None, message=None):
        self.comment = comment
        self.message = message or "This comment requires moderation before it will be displayed."
        super().__init__(self.message)


class InvalidForm(CommentsError):
    """
    Exception raised when form validation fails.
    """
    def __init__(self, form=None, message=None):
        self.form = form
        self.message = message or "Invalid form data."
        super().__init__(self.message)


class MaximumThreadDepthExceeded(CommentsError):
    """
    Exception raised when the maximum comment thread depth is exceeded.
    """
    def __init__(self, message=None, max_depth=None):
        self.max_depth = max_depth
        self.message = message or f"Maximum thread depth of {max_depth} exceeded."
        super().__init__(self.message)


class RateLimitExceeded(CommentsError):
    """
    Exception raised when a user exceeds the rate limit for commenting.
    """
    def __init__(self, message=None, retry_after=None):
        self.retry_after = retry_after
        self.message = message or "Rate limit exceeded. Please try again later."
        super().__init__(self.message)


class UserBanned(CommentsError):
    """
    Exception raised when a banned user tries to comment.
    """
    pass