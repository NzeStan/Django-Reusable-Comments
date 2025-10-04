# Advanced Usage

This guide covers advanced usage patterns for Django Reusable Comments.

## Using Signals

Django Reusable Comments provides a robust signal system that you can use to extend its functionality.

### Available Signals

The package defines the following signals:

```python
from django_comments.signals import (
    comment_pre_save, comment_post_save, 
    comment_pre_delete, comment_post_delete,
    comment_flagged, comment_approved, comment_rejected
)
```

### Example Signal Handlers

#### Sending Notifications for New Comments

```python
from django.dispatch import receiver
from django.core.mail import send_mail
from django_comments.signals import comment_post_save

@receiver(comment_post_save)
def notify_on_new_comment(sender, comment, created, **kwargs):
    """Send an email notification when a new comment is created."""
    if created and comment.is_public:
        # Get the commented object owner (assuming it has a user field)
        content_object = comment.content_object
        if hasattr(content_object, 'user'):
            recipient = content_object.user.email
            
            # Send notification email
            send_mail(
                subject=f'New comment on your {content_object._meta.verbose_name}',
                message=f'User {comment.get_user_name()} commented: {comment.content[:100]}...',
                from_email='notifications@example.com',
                recipient_list=[recipient],
                fail_silently=True
            )
```

#### Custom Moderation Logic

```python
from django.dispatch import receiver
from django_comments.signals import comment_pre_save
from django_comments.signals import approve_comment, reject_comment

@receiver(comment_pre_save)
def auto_moderate_comments(sender, comment, **kwargs):
    """
    Automatically moderate comments based on custom rules.
    """
    # Skip if the comment is already being updated
    if comment.pk:
        return
        
    # Check for suspicious content (simplified example)
    suspicious_patterns = ['http://bit.ly', 'make money fast', 'work from home']
    
    for pattern in suspicious_patterns:
        if pattern.lower() in comment.content.lower():
            # Auto-reject comments with suspicious patterns
            comment.is_public = False
            break
    
    # Auto-approve comments from verified users (simplified example)
    if comment.user and comment.user.profile.is_verified:
        comment.is_public = True
```

#### Tracking Comment Flags

```python
from django.dispatch import receiver
from django_comments.signals import comment_flagged

@receiver(comment_flagged)
def handle_flagged_comment(sender, flag, comment, user, flag_type, reason, **kwargs):
    """
    Handle flagged comments - auto-hide after a threshold is reached.
    """
    # Count flags for this comment
    flag_count = comment.flags.count()
    
    # Auto-hide comments with more than 3 flags
    if flag_count >= 3 and comment.is_public:
        comment.is_public = False
        comment.save()
        
        # Log this action
        from django.utils import timezone
        import logging
        logger = logging.getLogger('django_comments')
        logger.warning(
            f"Comment {comment.pk} auto-hidden at {timezone.now()} "
            f"after reaching {flag_count} flags."
        )
```

## Custom Comment Managers

You can create custom managers to extend the built-in functionality:

```python
from django_comments.utils import get_comment_model

Comment = get_comment_model()

# Get all comments for a specific model instance
comments = Comment.objects.get_by_content_object(my_blog_post)

# Get only public comments
public_comments = Comment.objects.public()

# Get comments by a specific user
user_comments = Comment.objects.by_user(request.user)

# Get flagged comments
flagged_comments = Comment.objects.flagged()

# Search comments
search_results = Comment.objects.search("django")
```

## Working with Threaded Comments

Django Reusable Comments supports threaded comments with a hierarchical structure.

### Creating a Threaded Comment

```python
from django_comments.utils import get_comment_model

Comment = get_comment_model()

# Create a parent comment
parent_comment = Comment.objects.create_for_object(
    content_object=blog_post,
    user=request.user,
    content="This is a parent comment."
)

# Create a reply to the parent comment
child_comment = Comment.objects.create_for_object(
    content_object=blog_post,
    user=request.user,
    content="This is a reply.",
    parent=parent_comment
)
```

### Retrieving Comment Threads

```python
# Get all root comments (no parent)
root_comments = Comment.objects.root_nodes()

# Get all descendants of a comment
descendants = parent_comment.get_descendants()

# Get all ancestors of a comment
ancestors = child_comment.get_ancestors()

# Get the depth of a comment in the tree
depth = child_comment.depth  # Should be 1 (parent is at depth 0)
```

## Custom API Endpoints

If you need custom API endpoints, you can create your own views that use the existing serializers:

```python
# myapp/api.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django_comments.api.serializers import CommentSerializer
from django_comments.utils import get_comment_model

Comment = get_comment_model()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_comments(request):
    """
    Custom endpoint to get comments made by the current user.
    """
    comments = Comment.objects.by_user(request.user)
    serializer = CommentSerializer(comments, many=True, context={'request': request})
    return Response(serializer.data)

# Then add to your URLs
# urls.py
from django.urls import path
from myapp.api import user_comments

urlpatterns = [
    # ...
    path('api/my-comments/', user_comments, name='my-comments'),
    # ...
]
```

## Integrating with Other Django Apps

### Django REST Framework Filters

Django Reusable Comments integrates with django-filter for API filtering. You can extend the filter set:

```python
from django_filter import rest_framework as filters
from django_comments.api.filtersets import CommentFilterSet

class ExtendedCommentFilterSet(CommentFilterSet):
    rating = filters.NumberFilter(field_name='rating')  # Assuming you have a custom comment model with rating
    rating_gte = filters.NumberFilter(field_name='rating', lookup_expr='gte')
    
    class Meta(CommentFilterSet.Meta):
        fields = CommentFilterSet.Meta.fields + ['rating']
```

### Django REST Framework Permissions

You can customize permissions for comments by extending the existing permission classes:

```python
from rest_framework import permissions
from django_comments.api.permissions import CommentPermission

class CustomCommentPermission(CommentPermission):
    def has_permission(self, request, view):
        # First check the parent class permissions
        if not super().has_permission(request, view):
            return False
            
        # Add custom permission logic
        if view.action == 'create':
            # Only allow premium users to create comments
            return request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.is_premium
            
        return True
```

## Integration with Front-end Frameworks

### Using Django Reusable Comments with React

Here's a basic React component that interacts with the API:

```jsx
// CommentsList.jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const CommentsList = ({ contentType, objectId }) => {
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newComment, setNewComment] = useState('');
  
  useEffect(() => {
    const fetchComments = async () => {
      try {
        const response = await axios.get(
          `/api/content/${contentType}/${objectId}/comments/`
        );
        setComments(response.data.results);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching comments:', error);
        setLoading(false);
      }
    };
    
    fetchComments();
  }, [contentType, objectId]);
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      const response = await axios.post('/api/comments/', {
        content_type: contentType,
        object_id: objectId,
        content: newComment
      });
      
      setComments([response.data, ...comments]);
      setNewComment('');
    } catch (error) {
      console.error('Error posting comment:', error);
    }
  };
  
  if (loading) return <div>Loading comments...</div>;
  
  return (
    <div className="comments-section">
      <h3>Comments ({comments.length})</h3>
      
      <form onSubmit={handleSubmit}>
        <textarea
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          required
          placeholder="Write a comment..."
        ></textarea>
        <button type="submit">Post Comment</button>
      </form>
      
      <div className="comments-list">
        {comments.map(comment => (
          <div key={comment.id} className="comment">
            <div className="comment-header">
              <span className="comment-author">{comment.user_info?.display_name || comment.user_name}</span>
              <span className="comment-date">{new Date(comment.created_at).toLocaleString()}</span>
            </div>
            <div className="comment-content">{comment.content}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CommentsList;
```

## Performance Optimization

### Database Optimization

For large comment systems, consider these optimizations:

1. **Add indexes** to fields frequently used in filtering and ordering:

```python
class Comment(AbstractCommentBase):
    # ... other fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['user']),
            models.Index(fields=['is_public', 'is_removed']),
            models.Index(fields=['thread_id']),
        ]
```

2. **Use select_related/prefetch_related** when retrieving comments to minimize database queries:

```python
# In your view or serializer
comments = Comment.objects.select_related('user', 'content_type').filter(...)
```

3. **Implement caching** for frequently accessed comment data:

```python
from django.core.cache import cache

def get_comments_for_object(content_object):
    cache_key = f'comments_for_{content_object._meta.model_name}_{content_object.pk}'
    comments = cache.get(cache_key)
    
    if comments is None:
        comments = Comment.objects.filter(
            content_type=ContentType.objects.get_for_model(content_object),
            object_id=content_object.pk,
            is_public=True,
            is_removed=False
        ).select_related('user')
        
        cache.set(cache_key, comments, 60 * 15)  # Cache for 15 minutes
        
    return comments
```

## Custom Comment Templates

If you're using Django's template system, you can override the default templates by creating your own in your project:

```
templates/
└── django_comments/