from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Count, Q, Prefetch, Subquery, OuterRef, Exists, IntegerField, CharField
from django.db.models.functions import Cast


class CommentQuerySet(models.QuerySet):
    """
    Custom QuerySet for Comment model with performance optimizations.
    FIXED: All flag-related methods now properly handle UUID primary keys.
    """
    
    def with_user_and_content_type(self):
        """
        Optimize foreign key access.
        Use this for any query that will access user or content_type.
        """
        return self.select_related('user', 'content_type')
    
    def with_parent_info(self):
        """
        Optimize parent comment access with user info.
        Use this for threaded comment displays.
        """
        return self.select_related('parent', 'parent__user')
    
    def with_flags(self):
        """
        Optimize flag-related queries.
        Use this when you need to display or count flags.
        """
        from django_comments.models import CommentFlag
        return self.prefetch_related(
            Prefetch(
                'flags',
                queryset=CommentFlag.objects.select_related('user')
            )
        )
    
    def with_children_count(self):
        """
        Annotate with children count.
        Use this for displaying reply counts without extra queries.
        """
        return self.annotate(
            children_count_annotated=Count('children', distinct=True)
        )
    
    def optimized_for_list(self):
        """
        FIXED: Comprehensive optimization for list views.
        
        Main fix: Uses Subquery with explicit UUID-to-string casting for flag counts.
        This fixes the "flags always 0" bug.
        """
        from django_comments.models import CommentFlag
        
        # Get ContentType for Comment model
        comment_ct = ContentType.objects.get_for_model(self.model)
        
        # CRITICAL FIX: Use Subquery with Cast to properly match UUID to string
        flags_subquery = CommentFlag.objects.filter(
            comment_type=comment_ct,
            # Cast UUID primary key to string for proper matching
            comment_id=Cast(OuterRef('pk'), CharField())
        ).values('comment_id').annotate(
            count=Count('id')
        ).values('count')
        
        return self.select_related(
            'user',
            'content_type',
            'parent',
            'parent__user'
        ).prefetch_related(
            Prefetch(
                'flags',
                queryset=CommentFlag.objects.select_related('user')
            )
        ).annotate(
            # Use Subquery instead of Count('flags') for proper UUID matching
            flags_count_annotated=Subquery(
                flags_subquery,
                output_field=IntegerField()
            ),
            children_count_annotated=Count('children', distinct=True)
        )
    
    def for_model(self, model_or_instance):
        """
        Return all comments for a specific model or model instance.
        Includes basic optimizations.
        """
        if isinstance(model_or_instance, models.Model):
            # It's a model instance
            model = model_or_instance.__class__
            content_type = ContentType.objects.get_for_model(model)
            return self.filter(
                content_type=content_type,
                object_id=str(model_or_instance.pk) 
            ).with_user_and_content_type()
        else:
            # It's a model class
            content_type = ContentType.objects.get_for_model(model_or_instance)
            return self.filter(
                content_type=content_type
            ).with_user_and_content_type()
    
    def public(self):
        """
        Return only public, non-removed comments.
        Includes basic optimizations.
        """
        return self.filter(
            is_public=True, 
            is_removed=False
        ).with_user_and_content_type()
    
    def removed(self):
        """
        Return only removed comments.
        """
        return self.filter(is_removed=True).with_user_and_content_type()
    
    def not_public(self):
        """
        Return non-public comments (moderation queue).
        """
        return self.filter(
            is_public=False, 
            is_removed=False
        ).with_user_and_content_type()
    
    def flagged(self):
        """
        FIXED: Return comments that have been flagged.
        Uses Exists subquery instead of Count for proper UUID matching.
        """
        from django_comments.models import CommentFlag
        
        comment_ct = ContentType.objects.get_for_model(self.model)
        
        # Use Exists instead of Count for better performance and UUID compatibility
        has_flags = Exists(
            CommentFlag.objects.filter(
                comment_type=comment_ct,
                comment_id=Cast(OuterRef('pk'), CharField())
            )
        )
        
        return self.annotate(
            has_flags=has_flags
        ).filter(
            has_flags=True
        ).with_user_and_content_type().with_flags()
    
    def root_nodes(self):
        """
        Return only root comments (no parent).
        Includes basic optimizations.
        """
        return self.filter(
            parent__isnull=True
        ).with_user_and_content_type()
    
    def by_user(self, user):
        """
        Return comments by a specific user.
        Includes basic optimizations.
        """
        return self.filter(user=user).with_user_and_content_type()
    
    def by_thread(self, thread_id):
        """
        Return comments belonging to a specific thread.
        Includes basic optimizations.
        """
        return self.filter(
            thread_id=thread_id
        ).with_user_and_content_type().with_parent_info()
    
    def search(self, query):
        """
        Search for comments by content or username.
        Includes basic optimizations.
        """
        return self.filter(
            Q(content__icontains=query) | 
            Q(user_name__icontains=query) |
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query)
        ).with_user_and_content_type()
    
    def with_full_thread(self):
        """
        Optimize for displaying full comment threads.
        Includes parent, children, and all related data.
        """
        from django_comments.models import CommentFlag, Comment
        
        return self.select_related(
            'user',
            'content_type',
            'parent',
            'parent__user'
        ).prefetch_related(
            Prefetch(
                'children',
                queryset=Comment.objects.select_related('user').filter(
                    is_public=True,
                    is_removed=False
                )
            ),
            Prefetch(
                'flags',
                queryset=CommentFlag.objects.select_related('user')
            )
        ).annotate(
            children_count_annotated=Count('children', distinct=True)
        )
    
    def visible_to_user(self, user):
        """Return comments visible to a specific user."""
        # Staff and superusers see everything
        if hasattr(user, 'is_authenticated') and user.is_authenticated:
            if user.is_staff or user.is_superuser:
                return self
        
        # Anonymous users only see public, non-removed
        if not hasattr(user, 'is_authenticated') or not user.is_authenticated:
            return self.filter(is_public=True, is_removed=False)
        
        # Authenticated regular users see public + their own
        return self.filter(
            Q(is_public=True, is_removed=False) |
            Q(user=user)
        )

    def public_only(self):
        """Return only public, non-removed comments."""
        return self.filter(is_public=True, is_removed=False)


class CommentManager(models.Manager):
    """
    Custom Manager for Comment model.
    """
    
    def get_by_content_object(self, content_object):
        """
        Return all comments for a given object.
        """
        content_type = ContentType.objects.get_for_model(content_object)
        return self.filter(
            content_type=content_type,
            object_id=str(content_object.pk)  
        ).optimized_for_list()
    
    def get_by_model_and_id(self, model, object_id):
        """
        Return all comments for a given model and object_id.
        """
        content_type = ContentType.objects.get_for_model(model)
        return self.filter(
            content_type=content_type,
            object_id=str(object_id)  
        ).optimized_for_list()
    
    def create_for_object(self, content_object, **kwargs):
        """
        Create a new comment for a specific object.
        """
        content_type = ContentType.objects.get_for_model(content_object)
        return self.create(
            content_type=content_type,
            object_id=str(content_object.pk), 
            **kwargs
        )
    
    def get_public_for_object(self, content_object):
        """
        Get only public comments for an object.
        Common pattern, so worth having as dedicated method.
        """
        return self.get_by_content_object(content_object).filter(
            is_public=True,
            is_removed=False
        )
    
    def get_thread(self, thread_id):
        """
        Get all comments in a thread with full optimizations.
        """
        return self.filter(
            thread_id=thread_id
        ).with_full_thread().order_by('path')


class CommentFlagManager(models.Manager):
    """
    FIXED: Enhanced manager for CommentFlag with proper UUID handling.
    """
    
    def create_or_get_flag(self, comment, user, flag, reason=''):
        """
        Create a flag or raise ValidationError if it already exists.

        Args:
            comment: Comment instance
            user: User who is flagging
            flag: Flag type ('spam', 'offensive', etc.)
            reason: Optional reason for flagging

        Returns:
            tuple: (flag_obj, created)
        """
        from django.core.exceptions import ValidationError
        from django.contrib.contenttypes.models import ContentType

        comment_ct = ContentType.objects.get_for_model(comment)

        # ✅ 1. Check if flag already exists
        existing_flag = self.filter(
            comment_type=comment_ct,
            comment_id=str(comment.pk),  # CRITICAL: UUID must be string
            user=user,
            flag=flag
        ).first()

        if existing_flag:
            raise ValidationError(
                f"You have already flagged this comment as '{flag}'. "
                "You cannot flag the same comment multiple times with the same flag type."
            )

        # ✅ 2. Create flag if it doesn't exist
        flag_obj = self.create(
            comment_type=comment_ct,
            comment_id=str(comment.pk),
            user=user,
            flag=flag,
            reason=reason
        )

        return flag_obj, True

    
    def get_flags_for_comment(self, comment):
        """
        FIXED: Get all flags for a specific comment with proper UUID handling.
        
        Args:
            comment: Comment instance
        
        Returns:
            QuerySet of CommentFlag instances
        """
        comment_ct = ContentType.objects.get_for_model(comment)
        return self.filter(
            comment_type=comment_ct,
            comment_id=str(comment.pk)  # CRITICAL: Convert UUID to string
        ).select_related('user')
    
    def get_flags_by_user(self, user, flag_type=None):
        """
        Get all flags created by a specific user.
        
        Args:
            user: User instance
            flag_type: Optional flag type to filter by
        
        Returns:
            QuerySet of CommentFlag instances
        """
        queryset = self.filter(user=user).select_related(
            'user',
            'comment_type'
        )
        
        if flag_type:
            queryset = queryset.filter(flag=flag_type)
        
        return queryset
    
    def get_spam_flags(self):
        """Get all spam flags."""
        return self.filter(flag='spam').select_related('user', 'comment_type')
    
    def get_comments_with_multiple_flags(self, min_flags=2):
        """
        Get comments that have been flagged multiple times.
        Returns queryset with flag count annotation.
        
        Args:
            min_flags: Minimum number of flags to filter by
        
        Returns:
            QuerySet with flag_count annotation
        """
        return self.values(
            'comment_type', 'comment_id'
        ).annotate(
            flag_count=Count('id')
        ).filter(
            flag_count__gte=min_flags
        ).order_by('-flag_count')