from rest_framework import permissions

from ..conf import comments_settings


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of a comment to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner
        return obj.user == request.user


class CommentPermission(permissions.BasePermission):
    """
    Permission for comments API.
    - Anyone can list and retrieve public comments
    - Authenticated users can create comments (unless anonymous comments are allowed)
    - Only the owner, staff, or users with permission can edit/delete comments
    - Only users with moderation permission can approve/reject comments
    """
    
    def has_permission(self, request, view):
        # Everyone can list and retrieve comments
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # For comment creation (POST)
        if request.method == 'POST' and view.action == 'create':
            # Allow anonymous comments if setting is enabled
            if comments_settings.ALLOW_ANONYMOUS:
                return True
            # Otherwise, require authentication
            return request.user.is_authenticated
        
        # For all other actions, require authentication
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Staff and superusers can do anything
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # For edit/update actions
        if request.method in ['PUT', 'PATCH'] and view.action in ['update', 'partial_update']:
            # Only the comment owner can edit
            return obj.user == request.user
        
        # For delete action
        if request.method == 'DELETE' and view.action == 'destroy':
            # Only the comment owner can delete
            return obj.user == request.user
        
        # For moderation actions (approve/reject)
        if view.action in ['approve', 'reject']:
            # Allow the request to proceed - the view will check has_perm
            return True
        
        # For flag action
        if view.action == 'flag':
            # Users can flag any comment, but must be authenticated
            return request.user.is_authenticated
        
        return False


class ModeratorPermission(permissions.BasePermission):
    """
    Permission for comment moderation actions.
    Only users with the 'can_moderate_comments' permission can perform these actions.
    """
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            (request.user.is_staff or 
             request.user.is_superuser or 
             request.user.has_perm('django_comments.can_moderate_comments'))
        )