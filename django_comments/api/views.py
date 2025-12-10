from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from ..conf import comments_settings
from ..exceptions import CommentModerated
from ..models import CommentFlag, BannedUser, CommentRevision, ModerationAction
from ..signals import flag_comment, approve_comment, reject_comment
from ..utils import (
    get_comment_model,
    get_model_from_content_type_string,
    can_edit_comment,
    create_comment_revision,
    log_moderation_action,
)
from rest_framework import serializers as drf_serializers
import uuid
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.db.models import Count
from rest_framework import status
from ..drf_integration import get_comment_pagination_class, CommentPagination
from .serializers import (
    CommentSerializer, 
    CommentFlagSerializer,
    CreateCommentFlagSerializer,
    BannedUserSerializer,
)
from django.db import transaction 
from .permissions import (
    CommentPermission, 
)
from .filtersets import CommentFilterSet

Comment = get_comment_model()


def get_user_groups_cached(user, request):
    """
    Get user groups with request-level caching.
    Uses request cache instead of modifying user object.
    """
    if not user.is_authenticated:
        return set()
    
    # Use request as cache storage (thread-safe, request-scoped)
    cache_key = f'_user_groups_{user.pk}'
    
    if not hasattr(request, '_cache'):
        request._cache = {}
    
    if cache_key not in request._cache:
        request._cache[cache_key] = set(
            user.groups.values_list('name', flat=True)
        )
    
    return request._cache[cache_key]

# ADD this helper function at the TOP of views.py (after imports, before CommentViewSet class)

def validate_comment_ids(comment_ids, max_count=100):
    """
    Validate a list of comment IDs for bulk operations.
    
    Security checks:
    - Ensures input is a list
    - Limits number of IDs to prevent DoS
    - Validates each ID is a valid UUID format
    - Prevents SQL injection and invalid queries
    
    Args:
        comment_ids: List of comment IDs (strings or UUIDs)
        max_count: Maximum allowed IDs (default 100)
    
    Returns:
        list: List of validated UUID objects
    
    Raises:
        serializers.ValidationError: If validation fails
    
    Example:
        >>> ids = ['123e4567-e89b-12d3-a456-426614174000', 'invalid']
        >>> validate_comment_ids(ids)  # Raises ValidationError
    """
    # Check 1: Must be a list
    if not isinstance(comment_ids, list):
        raise drf_serializers.ValidationError({
            'comment_ids': _("Must be a list of comment IDs")
        })
    
    # Check 2: Cannot be empty
    if not comment_ids:
        raise drf_serializers.ValidationError({
            'comment_ids': _("List cannot be empty")
        })
    
    # Check 3: Length limit to prevent DoS
    if len(comment_ids) > max_count:
        raise drf_serializers.ValidationError({
            'comment_ids': _(
                f"Cannot process more than {max_count} comments at once. "
                f"You provided {len(comment_ids)} IDs."
            )
        })
    
    # Check 4: Validate each ID is a valid UUID
    validated_ids = []
    invalid_ids = []
    
    for i, cid in enumerate(comment_ids):
        try:
            # Convert to UUID - this validates the format
            validated_uuid = uuid.UUID(str(cid))
            validated_ids.append(validated_uuid)
        except (ValueError, AttributeError, TypeError) as e:
            # Track invalid IDs for better error message
            invalid_ids.append({
                'index': i,
                'value': str(cid)[:50],  # Truncate for safety
                'error': str(e)
            })
    
    # If any invalid IDs, raise detailed error
    if invalid_ids:
        raise drf_serializers.ValidationError({
            'comment_ids': _(
                f"Found {len(invalid_ids)} invalid UUID(s). "
                "All IDs must be valid UUIDs."
            ),
            'invalid_ids': invalid_ids[:5]  # Show first 5 for debugging
        })
    
    return validated_ids

class CommentViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing comments.
    Optimized with select_related, prefetch_related, and annotations.
    validates ordering against ALLOWED_SORTS.
    """
    serializer_class = CommentSerializer
    permission_classes = [CommentPermission]
    filterset_class = CommentFilterSet
    pagination_class = get_comment_pagination_class()
    filter_backends = [
        DjangoFilterBackend, 
        filters.SearchFilter,
        filters.OrderingFilter
    ]
    search_fields = ['content', 'user_name', 'user__username', 'user__first_name', 'user__last_name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_ordering(self):
        """
        Get ordering with validation against ALLOWED_SORTS.
        Enforces ALLOWED_SORTS setting.
        """
        ordering = self.request.query_params.get('ordering', None)
        
        if ordering:
            # Validate against ALLOWED_SORTS if configured
            allowed_sorts = comments_settings.ALLOWED_SORTS
            if allowed_sorts and ordering not in allowed_sorts:
                # Return default ordering if invalid sort requested
                return [comments_settings.DEFAULT_SORT]
            return [ordering]
        
        # Return default
        return [comments_settings.DEFAULT_SORT]
    
    def get_queryset(self):
        """
        Get optimized queryset with all related data preloaded.
        Reduces N+1 queries dramatically.
        """
        queryset = Comment.objects.all()
        user = self.request.user
        
        queryset = queryset.select_related(
            'user',              
            'content_type',     
            'parent',            
            'parent__user'    
        )
        
        queryset = queryset.prefetch_related(
            models.Prefetch(
                'flags',
                queryset=CommentFlag.objects.select_related('user')
            )
        )

        
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
        
        if not user.is_staff and not user.is_superuser:
            can_see_non_public = False
            
            if not user.is_anonymous:
                user_groups = get_user_groups_cached(user, self.request)
                
                # Check if user is in privileged groups
                privileged_groups = set(comments_settings.CAN_VIEW_NON_PUBLIC_COMMENTS)
                can_see_non_public = bool(user_groups & privileged_groups)
            
            if not can_see_non_public:
                if user.is_anonymous:
                    queryset = queryset.filter(is_public=True, is_removed=False)
                else:
                    queryset = queryset.filter(
                        models.Q(is_public=True, is_removed=False) |
                        models.Q(user=user)
                    )
        
        # Apply validated ordering
        ordering = self.get_ordering()
        queryset = queryset.order_by(*ordering)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """
        Create a new comment, handling moderation exceptions.
        """
        try:
            return super().create(request, *args, **kwargs)
        except CommentModerated as e:
            # Comment was created but requires moderation
            # Return 201 with the comment data and moderation message
            serializer = self.get_serializer(e.comment)
            headers = self.get_success_headers(serializer.data)
            return Response(
                {
                    'detail': str(e.message),
                    'comment': serializer.data,
                    'requires_moderation': True
                },
                status=status.HTTP_201_CREATED,
                headers=headers
            )
    
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
    

    def check_user_ban_cached(self, user):
        """
        Check if user is banned with request-level caching.
        
        ✅ UPDATED: Now uses BannedUser.check_user_banned() from models
        """
        if not hasattr(self.request, '_ban_cache'):
            self.request._ban_cache = {}
        
        user_id = user.pk
        if user_id not in self.request._ban_cache:
            # ✅ NEW: Use BannedUser.check_user_banned() instead of utils
            self.request._ban_cache[user_id] = BannedUser.check_user_banned(user)
        
        return self.request._ban_cache[user_id]
    
    def get_serializer_context(self):
        """Add ban checking to serializer context."""
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            # ✅ SIMPLIFIED: Direct call without caching wrapper
            # BannedUser.check_user_banned already optimizes with select_related
            context['user_banned_info'] = BannedUser.check_user_banned(self.request.user)
        return context

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def flag(self, request, pk=None):
        """
        Flag a comment as inappropriate.
        Uses get_object() which already has prefetched data.
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
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def moderation_queue(self, request):
        """
        Get comments needing moderation.
        Returns pending, flagged, and spam-detected comments.
        """
        # Check moderation permission
        if not request.user.has_perm('django_comments.can_moderate_comments'):
            return Response(
                {'detail': _("You don't have permission to access the moderation queue.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Pending comments (awaiting approval)
        pending = Comment.objects.filter(
            is_public=False,
            is_removed=False
        ).optimized_for_list().order_by('-created_at')
        
        # Flagged comments (has flags, may or may not be public)
        flagged = Comment.objects.annotate(
            flag_count=models.Count('flags')
        ).filter(
            flag_count__gt=0
        ).optimized_for_list().order_by('-flag_count', '-created_at')
        
        # Spam-detected comments (auto-flagged)
        spam_detected = Comment.objects.filter(
            flags__flag='spam',
            flags__user__username='system'
        ).distinct().optimized_for_list().order_by('-created_at')
        
        # Apply pagination
        page_size = comments_settings.MODERATION_QUEUE_PAGE_SIZE
        
        return Response({
            'pending': {
                'count': pending.count(),
                'results': CommentSerializer(
                    pending[:page_size],
                    many=True,
                    context={'request': request}
                ).data
            },
            'flagged': {
                'count': flagged.count(),
                'results': CommentSerializer(
                    flagged[:page_size],
                    many=True,
                    context={'request': request}
                ).data
            },
            'spam_detected': {
                'count': spam_detected.count(),
                'results': CommentSerializer(
                    spam_detected[:page_size],
                    many=True,
                    context={'request': request}
                ).data
            }
        })


    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def bulk_approve(self, request):
        """
        Approve multiple comments at once.
        
        ✅ FIXED: Added comprehensive input validation
        
        Request body:
            {
                "comment_ids": ["uuid1", "uuid2", ...]
            }
        
        Returns:
            {
                "detail": "Success message",
                "approved_count": 5,
                "total_requested": 5,
                "not_found_count": 0
            }
        
        Permissions:
            - User must be authenticated
            - User must have 'can_moderate_comments' permission
        
        Errors:
            - 403: No permission
            - 400: Invalid input (not list, invalid UUIDs, too many IDs)
            - 404: Some comment IDs not found
        """
        # Check moderation permission
        if not request.user.has_perm('django_comments.can_moderate_comments'):
            return Response(
                {'detail': _("You don't have permission to moderate comments.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get comment IDs from request
        comment_ids = request.data.get('comment_ids', [])
        
        # ✅ FIXED: Validate input with comprehensive checks
        try:
            validated_ids = validate_comment_ids(comment_ids, max_count=100)
        except drf_serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        
        # Get comments from database
        comments = Comment.objects.filter(pk__in=validated_ids)
        found_count = comments.count()
        
        # ✅ IMPROVED: Track missing IDs for better error reporting
        if found_count != len(validated_ids):
            found_ids = set(str(c.pk) for c in comments)
            missing_ids = [str(vid) for vid in validated_ids if str(vid) not in found_ids]
            
            return Response(
                {
                    'detail': _("Some comment IDs were not found"),
                    'requested': len(validated_ids),
                    'found': found_count,
                    'missing_count': len(missing_ids),
                    'missing_ids': missing_ids[:10]  # Show first 10
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Approve comments (only non-public ones)
        approved_count = 0
        already_public = 0
        
        for comment in comments:
            if not comment.is_public:
                approve_comment(comment, moderator=request.user)
                approved_count += 1
            else:
                already_public += 1
        
        # Return success with detailed stats
        return Response({
            'detail': _("Successfully approved {count} comment(s).").format(
                count=approved_count
            ),
            'approved_count': approved_count,
            'already_public': already_public,
            'total_requested': len(validated_ids)
        })



    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def bulk_reject(self, request):
        """
        Reject multiple comments at once.
        
        ✅ FIXED: Added comprehensive input validation
        
        Request body:
            {
                "comment_ids": ["uuid1", "uuid2", ...],
                "reason": "Optional rejection reason"
            }
        
        Returns:
            {
                "detail": "Success message",
                "rejected_count": 5,
                "total_requested": 5
            }
        
        Permissions:
            - User must be authenticated
            - User must have 'can_moderate_comments' permission
        
        Errors:
            - 403: No permission
            - 400: Invalid input (not list, invalid UUIDs, too many IDs)
            - 404: Some comment IDs not found
        """
        # Check moderation permission
        if not request.user.has_perm('django_comments.can_moderate_comments'):
            return Response(
                {'detail': _("You don't have permission to moderate comments.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get comment IDs and optional reason from request
        comment_ids = request.data.get('comment_ids', [])
        reason = request.data.get('reason', '')
        
        # ✅ FIXED: Validate input
        try:
            validated_ids = validate_comment_ids(comment_ids, max_count=100)
        except drf_serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        
        # ✅ IMPROVED: Validate reason length
        if reason and len(reason) > 1000:
            return Response(
                {'detail': _("Reason must be 1000 characters or less")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get comments from database
        comments = Comment.objects.filter(pk__in=validated_ids)
        found_count = comments.count()
        
        # Check if all comments were found
        if found_count != len(validated_ids):
            found_ids = set(str(c.pk) for c in comments)
            missing_ids = [str(vid) for vid in validated_ids if str(vid) not in found_ids]
            
            return Response(
                {
                    'detail': _("Some comment IDs were not found"),
                    'requested': len(validated_ids),
                    'found': found_count,
                    'missing_count': len(missing_ids),
                    'missing_ids': missing_ids[:10]
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Reject comments (only public ones)
        rejected_count = 0
        already_rejected = 0
        
        for comment in comments:
            if comment.is_public:
                reject_comment(comment, moderator=request.user)
                
                # Log with reason if provided
                if reason:
                    log_moderation_action(
                        comment=comment,
                        moderator=request.user,
                        action='rejected',
                        reason=reason
                    )
                
                rejected_count += 1
            else:
                already_rejected += 1
        
        # Return success with detailed stats
        return Response({
            'detail': _("Successfully rejected {count} comment(s).").format(
                count=rejected_count
            ),
            'rejected_count': rejected_count,
            'already_rejected': already_rejected,
            'total_requested': len(validated_ids),
            'reason_provided': bool(reason)
        })


    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def bulk_delete(self, request):
        """
        Delete multiple comments at once with moderation logging.
        
        ✅ FIXED: Added comprehensive input validation
        
        Request body:
            {
                "comment_ids": ["uuid1", "uuid2", ...],
                "reason": "Optional deletion reason"
            }
        
        Returns:
            {
                "detail": "Success message",
                "deleted_count": 5,
                "total_requested": 5
            }
        
        Permissions:
            - User must be authenticated
            - User must have 'can_moderate_comments' permission
        
        Errors:
            - 403: No permission
            - 400: Invalid input (not list, invalid UUIDs, too many IDs)
            - 404: Some comment IDs not found
            - 500: Database error during deletion
        
        Notes:
            - This is a destructive action that cannot be undone
            - All moderation actions are logged before deletion
            - Deletes are performed in a transaction for safety
        """
        # Check moderation permission
        if not request.user.has_perm('django_comments.can_moderate_comments'):
            return Response(
                {'detail': _("You don't have permission to moderate comments.")},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get comment IDs and optional reason from request
        comment_ids = request.data.get('comment_ids', [])
        reason = request.data.get('reason', '')

        # ✅ FIXED: Validate input
        try:
            validated_ids = validate_comment_ids(comment_ids, max_count=100)
        except drf_serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        
        # ✅ IMPROVED: Validate reason length
        if reason and len(reason) > 1000:
            return Response(
                {'detail': _("Reason must be 1000 characters or less")},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get comments from database
        comments_qs = Comment.objects.filter(pk__in=validated_ids)

        if not comments_qs.exists():
            return Response(
                {'detail': _("No comments found for the provided IDs.")},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # ✅ IMPROVED: Check if all comments exist
        found_count = comments_qs.count()
        if found_count != len(validated_ids):
            found_ids = set(str(c.pk) for c in comments_qs)
            missing_ids = [str(vid) for vid in validated_ids if str(vid) not in found_ids]
            
            return Response(
                {
                    'detail': _("Some comment IDs were not found"),
                    'requested': len(validated_ids),
                    'found': found_count,
                    'missing_count': len(missing_ids),
                    'missing_ids': missing_ids[:10]
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Get content type and IP for logging
        comment_ct = ContentType.objects.get_for_model(Comment)
        ip_address = request.META.get('REMOTE_ADDR') or ''

        try:
            with transaction.atomic():
                # ✅ IMPROVED: Log moderation actions before deletion
                moderation_actions = []
                for comment in comments_qs:
                    moderation_actions.append(
                        ModerationAction(
                            comment_type=comment_ct,
                            comment_id=str(comment.pk),  # Ensure string for UUID
                            moderator=request.user,
                            action='deleted',
                            reason=reason or 'Bulk deletion',
                            ip_address=ip_address
                        )
                    )
                
                # Bulk create logs for efficiency
                ModerationAction.objects.bulk_create(moderation_actions)

                # Delete comments and get count
                deleted_count = comments_qs.count()
                comments_qs.delete()

        except Exception as e:
            # Log the error
            import logging
            logger = logging.getLogger(comments_settings.LOGGER_NAME)
            logger.error(f"Error during bulk delete: {e}")
            
            return Response(
                {
                    'detail': _("Error deleting comments: {error}").format(error=str(e)),
                    'error_type': type(e).__name__
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Return success with stats
        return Response({
            'detail': _("Successfully deleted {count} comment(s).").format(
                count=deleted_count
            ),
            'deleted_count': deleted_count,
            'total_requested': len(validated_ids),
            'reason_provided': bool(reason)
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def flag_stats(self, request):
        """
        Get flag statistics.
        """
        # Check moderation permission
        if not request.user.has_perm('django_comments.can_moderate_comments'):
            return Response(
                {'detail': _("You don't have permission to view flag statistics.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from ..models import CommentFlag
        
        # Total flags
        total_flags = CommentFlag.objects.count()
        
        # By type
        by_type = CommentFlag.objects.values('flag').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Top flagged comments
        top_flagged = Comment.objects.annotate(
            flag_count=Count('flags')
        ).filter(
            flag_count__gt=0
        ).order_by('-flag_count')[:10]
        
        # Unreviewed flags
        unreviewed_count = CommentFlag.objects.filter(reviewed=False).count()
        
        # Flags by day (last 30 days)
        from datetime import timedelta
        thirty_days_ago = timezone.now() - timedelta(days=30)
        flags_by_day = CommentFlag.objects.filter(
            created_at__gte=thirty_days_ago
        ).annotate(
            day=TruncDate('created_at')
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        return Response({
            'total_flags': total_flags,
            'unreviewed_count': unreviewed_count,
            'by_type': list(by_type),
            'top_flagged_comments': CommentSerializer(
                top_flagged,
                many=True,
                context={'request': request}
            ).data,
            'flags_by_day': list(flags_by_day),
        })


    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    def edit(self, request, pk=None):
        """
        Edit comment content with revision tracking.
        """
        comment = self.get_object()
        
        # Check if user can edit
        can_edit, reason = can_edit_comment(comment, request.user)
        if not can_edit:
            return Response(
                {'detail': reason},
                status=status.HTTP_403_FORBIDDEN
            )
        
        new_content = request.data.get('content')
        if not new_content:
            return Response(
                {'detail': _("Content is required.")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create revision before editing
        create_comment_revision(comment, edited_by=request.user)
        
        # Update content
        comment.content = new_content
        comment.save(update_fields=['content', 'updated_at'])
        
        # Log action
        log_moderation_action(
            comment=comment,
            moderator=request.user,
            action='edited',
            reason='User edited own comment'
        )
        
        serializer = self.get_serializer(comment)
        return Response(serializer.data)


    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def history(self, request, pk=None):
        """
        Get edit history for a comment.
        """
        comment = self.get_object()
        
        # Only owner or moderators can view history
        if comment.user != request.user and not request.user.has_perm('django_comments.can_moderate_comments'):
            return Response(
                {'detail': _("You don't have permission to view this comment's history.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from django.contrib.contenttypes.models import ContentType
        
        revisions = CommentRevision.objects.filter(
            comment_type=ContentType.objects.get_for_model(comment),
            comment_id=str(comment.pk)
        ).select_related('edited_by').order_by('-edited_at')
        
        from .serializers import CommentRevisionSerializer
        return Response(
            CommentRevisionSerializer(revisions, many=True).data
        )



class ContentObjectCommentsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    API endpoint for listing comments for a specific object.
    Optimized for performance with selective prefetching.
    validates ordering.
    """
    serializer_class = CommentSerializer
    permission_classes = [AllowAny]
    pagination_class = get_comment_pagination_class()
    filter_backends = [filters.OrderingFilter, 
                       filters.SearchFilter,]
    search_fields = ['content', 'user_name', 'user__username', 'user__first_name', 'user__last_name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = comments_settings.DEFAULT_SORT
    
    def get_ordering(self):
        """
        Get ordering with validation against ALLOWED_SORTS.
        """
        ordering = self.request.query_params.get('ordering', None)
        
        if ordering:
            allowed_sorts = comments_settings.ALLOWED_SORTS
            if allowed_sorts and ordering not in allowed_sorts:
                return [comments_settings.DEFAULT_SORT]
            return [ordering]
        
        return [comments_settings.DEFAULT_SORT]
    
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

        user = self.request.user
        if not user.is_staff and not user.is_superuser:
            queryset = queryset.filter(is_public=True, is_removed=False)
        
        thread_type = self.request.query_params.get('thread_type', 'tree')
        
        if thread_type == 'flat':
            # Return all comments
            pass
        elif thread_type == 'root':
            # Return only root comments
            queryset = queryset.filter(parent__isnull=True)
        else:  # 'tree' is default
            # For tree view, optionally filter by thread_id
            thread_id = self.request.query_params.get('thread_id')
            if thread_id:
                queryset = queryset.filter(thread_id=thread_id)
        
        # Apply validated ordering
        ordering = self.get_ordering()
        queryset = queryset.order_by(*ordering)
        
        return queryset
    


class FlagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for viewing and reviewing flags.
    """
    serializer_class = CommentFlagSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CommentPagination
    
    def get_queryset(self):
        """Only moderators can view flags."""
        if not self.request.user.has_perm('django_comments.can_moderate_comments'):
            return CommentFlag.objects.none()
        
        return CommentFlag.objects.select_related(
            'user',
            'comment_type',
            'reviewed_by'
        ).order_by('-created_at')
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def review(self, request, pk=None):
        """
        Mark a flag as reviewed.
        """
        if not request.user.has_perm('django_comments.can_moderate_comments'):
            return Response(
                {'detail': _("You don't have permission to review flags.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        flag = self.get_object()
        action = request.data.get('action')  # 'dismissed' or 'actioned'
        notes = request.data.get('notes', '')
        
        if action not in ['dismissed', 'actioned']:
            return Response(
                {'detail': _("Invalid action. Must be 'dismissed' or 'actioned'.")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        flag.mark_reviewed(
            moderator=request.user,
            action=action,
            notes=notes
        )
        
        return Response(
            CommentFlagSerializer(flag).data
        )


class BannedUserViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing banned users.
    """
    queryset = BannedUser.objects.select_related('user', 'banned_by').order_by('-created_at')
    serializer_class = BannedUserSerializer 
    permission_classes = [IsAuthenticated]
    pagination_class = CommentPagination
    
    def get_permissions(self):
        """Only moderators can manage bans."""
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAuthenticated()]  # Will check permission in method
    
    def get_queryset(self):
        """Moderators see all, users see only their own."""
        if self.request.user.has_perm('django_comments.can_moderate_comments'):
            return BannedUser.objects.select_related('user', 'banned_by').order_by('-created_at')
        
        return BannedUser.objects.filter(
            user=self.request.user
        ).select_related('banned_by')
    
    def create(self, request, *args, **kwargs):
        """Create a new ban."""
        if not request.user.has_perm('django_comments.can_moderate_comments'):
            return Response(
                {'detail': _("You don't have permission to ban users.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user_id = request.data.get('user_id')
        reason = request.data.get('reason', 'No reason provided')
        duration_days = request.data.get('duration_days')
        
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {'detail': _("User not found.")},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Calculate ban expiry
        banned_until = None
        if duration_days:
            from datetime import timedelta
            banned_until = timezone.now() + timedelta(days=int(duration_days))
        
        # Create ban
        ban = BannedUser.objects.create(
            user=user,
            banned_until=banned_until,
            reason=reason,
            banned_by=request.user
        )
        
        # Log action
        log_moderation_action(
            comment=None,
            moderator=request.user,
            action='banned_user',
            reason=reason,
            affected_user=user,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        # Notify user
        from ..notifications import notify_user_banned
        notify_user_banned(ban)
        
        from .serializers import BannedUserSerializer
        return Response(
            BannedUserSerializer(ban).data,
            status=status.HTTP_201_CREATED
        )
    
    def destroy(self, request, *args, **kwargs):
        """Unban a user."""
        if not request.user.has_perm('django_comments.can_moderate_comments'):
            return Response(
                {'detail': _("You don't have permission to unban users.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        ban = self.get_object()
        
        # Store ban info for notification before deletion
        unbanned_user = ban.user
        original_ban_reason = ban.reason
        
        # Log action
        log_moderation_action(
            comment=None,
            moderator=request.user,
            action='unbanned_user',
            reason=f"Unbanned: {ban.reason}",
            affected_user=ban.user,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        # Delete the ban (actually unbans the user)
        result = super().destroy(request, *args, **kwargs)
        
        # ✅ NEW: Send unban notification
        from ..notifications import notify_user_unbanned
        notify_user_unbanned(
            user=unbanned_user,
            unbanned_by=request.user,
            original_ban_reason=original_ban_reason
        )
        
        return result