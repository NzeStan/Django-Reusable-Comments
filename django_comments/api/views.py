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
from ..models import CommentFlag
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
    Optimized with select_related, prefetch_related, and annotations.
    """
    serializer_class = CommentSerializer
    permission_classes = [CommentPermission]
    filterset_class = CommentFilterSet
    filter_backends = [
        DjangoFilterBackend, 
        filters.SearchFilter,
        filters.OrderingFilter
    ]
    # FIXED: Include user__username in search fields
    search_fields = ['content', 'user_name', 'user__username', 'user__first_name', 'user__last_name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Get optimized queryset with all related data preloaded.
        Reduces N+1 queries dramatically.
        """
        queryset = Comment.objects.all()
        user = self.request.user
        
        # ==========================================
        # PERFORMANCE OPTIMIZATION
        # ==========================================
        
        # 1. Select related foreign keys (single-value relationships)
        queryset = queryset.select_related(
            'user',              # Comment author
            'content_type',      # Type of commented object
            'parent',            # Parent comment for threading
            'parent__user'       # Parent comment's author (for nested display)
        )
        
        # 2. Prefetch many-to-many and reverse foreign keys
        queryset = queryset.prefetch_related(
            models.Prefetch(
                'flags',
                queryset=CommentFlag.objects.select_related('user')
            )
        )
        
        # 3. Add annotations for computed fields
        # This prevents extra queries in serializers
        queryset = queryset.annotate(
            flags_count_annotated=models.Count('flags', distinct=True),
            children_count_annotated=models.Count('children', distinct=True)
        )
        
        # 4. Action-specific optimizations
        if self.action == 'retrieve':
            # For detail view, also prefetch children with their users
            queryset = queryset.prefetch_related(
                models.Prefetch(
                    'children',
                    queryset=Comment.objects.select_related('user').filter(
                        is_public=True,
                        is_removed=False
                    ).order_by('created_at')
                )
            )
        
        # ==========================================
        # PERMISSION FILTERING
        # ==========================================
        
        if not user.is_staff and not user.is_superuser:
            can_see_non_public = False
            
            if not user.is_anonymous:
                # Cache user groups to avoid repeated queries
                if not hasattr(user, '_cached_group_names'):
                    user._cached_group_names = set(
                        user.groups.values_list('name', flat=True)
                    )
                
                # Check if user is in privileged groups
                privileged_groups = set(comments_settings.CAN_VIEW_NON_PUBLIC_COMMENTS)
                can_see_non_public = bool(user._cached_group_names & privileged_groups)
            
            if not can_see_non_public:
                if user.is_anonymous:
                    queryset = queryset.filter(is_public=True, is_removed=False)
                else:
                    queryset = queryset.filter(
                        models.Q(is_public=True, is_removed=False) |
                        models.Q(user=user)
                    )
        
        return queryset
    
    def perform_create(self, serializer):
        """
        Create a new comment, handling moderation if needed.
        """
        # Add request metadata
        ip_address = self.request.META.get('REMOTE_ADDR', None)
        user_agent = self.request.META.get('HTTP_USER_AGENT', '')
        
        # Create the comment
        comment = serializer.save(
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Handle moderation workflow
        if comments_settings.MODERATOR_REQUIRED and not comment.is_public:
            raise CommentModerated(
                comment=comment,
                message=_("Your comment has been submitted and is awaiting moderation.")
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def flag(self, request, pk=None):
        """
        Flag a comment as inappropriate.
        Optimized: Uses get_object() which already has prefetched data.
        """
        comment = self.get_object()
        
        serializer = CreateCommentFlagSerializer(
            data=request.data,
            context={'request': request, 'comment': comment}
        )
        
        if serializer.is_valid():
            flag_obj = flag_comment(
                comment=comment,
                user=request.user,
                flag=serializer.validated_data.get('flag', 'other'),
                reason=serializer.validated_data.get('reason', '')
            )
            
            return Response(
                CommentFlagSerializer(flag_obj).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        """
        Approve a comment (make it public).
        """
        comment = self.get_object()
        
        # Check permissions
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
        
        # Check permissions
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
    Optimized for performance with selective prefetching.
    """
    serializer_class = CommentSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']
    ordering = comments_settings.DEFAULT_SORT
    
    def get_queryset(self):
        """
        Get all comments for a specific object with optimizations.
        """
        content_type_str = self.kwargs.get('content_type')
        object_id = self.kwargs.get('object_id')
        
        # Get the model from the content type string
        model = get_model_from_content_type_string(content_type_str)
        if not model:
            return Comment.objects.none()
        
        # Get the content type
        content_type = ContentType.objects.get_for_model(model)
        
        # Build base queryset
        queryset = Comment.objects.filter(
            content_type=content_type,
            object_id=object_id
        )
        
        # ==========================================
        # PERFORMANCE OPTIMIZATION
        # ==========================================
        queryset = queryset.select_related(
            'user',
            'content_type',
            'parent',
            'parent__user'
        ).prefetch_related(
            models.Prefetch(
                'flags',
                queryset=CommentFlag.objects.select_related('user')
            )
        ).annotate(
            flags_count_annotated=models.Count('flags', distinct=True),
            children_count_annotated=models.Count('children', distinct=True)
        )
        
        # ==========================================
        # PERMISSION FILTERING
        # ==========================================
        user = self.request.user
        if not user.is_staff and not user.is_superuser:
            queryset = queryset.filter(is_public=True, is_removed=False)
        
        # ==========================================
        # THREAD TYPE FILTERING
        # ==========================================
        thread_type = self.request.query_params.get('thread_type', 'tree')
        
        if thread_type == 'flat':
            # Return all comments (already done)
            pass
        elif thread_type == 'root':
            # Return only root comments
            queryset = queryset.filter(parent__isnull=True)
        else:  # 'tree' is default
            # For tree view, optionally filter by thread_id
            thread_id = self.request.query_params.get('thread_id')
            if thread_id:
                queryset = queryset.filter(thread_id=thread_id)
        
        return queryset