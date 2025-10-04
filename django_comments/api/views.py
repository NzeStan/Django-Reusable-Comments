from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from ..conf import comments_settings
from ..exceptions import CommentModerated
from ..signals import flag_comment, approve_comment, reject_comment
from ..utils import (
    get_comment_model,
    get_model_from_content_type_string,
    get_object_from_content_type_and_id,
    check_comment_permissions
)
from .serializers import (
    CommentSerializer, 
    CommentFlagSerializer,
    CreateCommentFlagSerializer,
)
from .permissions import (
    CommentPermission, 
    IsOwnerOrReadOnly
)
from .filtersets import CommentFilterSet

Comment = get_comment_model()


class CommentViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing comments.
    """
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [CommentPermission]
    filterset_class = CommentFilterSet
    filter_backends = [
        DjangoFilterBackend, 
        filters.SearchFilter,
        filters.OrderingFilter
    ]
    search_fields = ['content', 'user_name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Get the list of comments based on user permissions.
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # If user is not staff or superuser, filter out non-public comments
        if not user.is_staff and not user.is_superuser:
            # Check if user is in any of the auto-approve groups
            can_see_non_public = False
            if not user.is_anonymous:
                user_groups = user.groups.values_list('name', flat=True)
                for group in comments_settings.CAN_VIEW_NON_PUBLIC_COMMENTS:
                    if group in user_groups:
                        can_see_non_public = True
                        break
            
            if not can_see_non_public:
                # Users can see all public comments and their own non-public comments
                if user.is_anonymous:
                    queryset = queryset.filter(is_public=True, is_removed=False)
                else:
                    queryset = queryset.filter(
                        (models.Q(is_public=True) & models.Q(is_removed=False)) |
                        models.Q(user=user)
                    )
        
        return queryset
    
    def perform_create(self, serializer):
        """
        Create a new comment, handling moderation if needed.
        """

        # DEBUG: Safe logging
        print("Request content type:", self.request.content_type)
        print("Parsed request data:", self.request.data)

        print("Content type from request:", repr(self.request.data.get('content_type')))
        print("Type of content_type:", type(self.request.data.get('content_type')))
        
        # Add request IP and user agent if available
        ip_address = self.request.META.get('REMOTE_ADDR', None)
        user_agent = self.request.META.get('HTTP_USER_AGENT', '')
        
        # Create the comment
        comment = serializer.save(
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # If moderation is required, raise a message
        if comments_settings.MODERATOR_REQUIRED and not comment.is_public:
            raise CommentModerated(
                comment=comment,
                message=_("Your comment has been submitted and is awaiting moderation.")
            )

    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def flag(self, request, pk=None):
        """
        Flag a comment as inappropriate.
        """
        comment = self.get_object()
        
        serializer = CreateCommentFlagSerializer(
            data=request.data,
            context={'request': request, 'comment': comment}
        )
        
        if serializer.is_valid():
            flag = flag_comment(
                comment=comment,
                user=request.user,
                flag=serializer.validated_data.get('flag', 'other'),
                reason=serializer.validated_data.get('reason', '')
            )
            
            return Response(
                CommentFlagSerializer(flag).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        """
        Approve a comment (make it public).
        """
        comment = self.get_object()
        
        # Check if user has permission to moderate
        if not request.user.has_perm('django_comments.can_moderate_comments'):
            return Response(
                {'detail': _("You don't have permission to moderate comments.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Approve the comment
        approve_comment(comment, moderator=request.user)
        
        return Response(
            {'detail': _("Comment approved successfully.")},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        """
        Reject a comment (make it non-public).
        """
        comment = self.get_object()
        
        # Check if user has permission to moderate
        if not request.user.has_perm('django_comments.can_moderate_comments'):
            return Response(
                {'detail': _("You don't have permission to moderate comments.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Reject the comment
        reject_comment(comment, moderator=request.user)
        
        return Response(
            {'detail': _("Comment rejected successfully.")},
            status=status.HTTP_200_OK
        )


class ContentObjectCommentsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    API endpoint for listing comments for a specific object.
    """
    serializer_class = CommentSerializer
    permission_classes = [AllowAny]
    filter_backends = [
        filters.OrderingFilter,
    ]
    ordering_fields = ['created_at', 'updated_at']
    ordering = comments_settings.DEFAULT_SORT
    
    def get_queryset(self):
        """
        Get all comments for a specific object.
        """
        content_type_str = self.kwargs.get('content_type')
        object_id = self.kwargs.get('object_id')
        
        # Get the model from the content type string
        model = get_model_from_content_type_string(content_type_str)
        if not model:
            return Comment.objects.none()
        
        # Get the content type
        content_type = ContentType.objects.get_for_model(model)
        
        # Get comments for this object
        queryset = Comment.objects.filter(
            content_type=content_type,
            object_id=object_id
        )
        
        # Filter by user permissions
        user = self.request.user
        if not user.is_staff and not user.is_superuser:
            queryset = queryset.filter(is_public=True, is_removed=False)
        
        # Filter by thread type if specified
        thread_type = self.request.query_params.get('thread_type', 'tree')
        if thread_type == 'flat':
            # Return all comments
            pass
        elif thread_type == 'root':
            # Return only root comments
            queryset = queryset.filter(parent__isnull=True)
        else:  # 'tree' is default
            # For tree view, include parent ID if provided to get specific thread
            thread_id = self.request.query_params.get('thread_id')
            if thread_id:
                queryset = queryset.filter(thread_id=thread_id)
        
        return queryset