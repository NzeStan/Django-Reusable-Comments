from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Count, Q, Prefetch


class CommentQuerySet(models.QuerySet):
    """
    Custom QuerySet for Comment model with performance optimizations.
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
        from .models import CommentFlag
        return self.prefetch_related(
            Prefetch(
                'flags',
                queryset=CommentFlag.objects.select_related('user')
            )
        ).annotate(
            flags_count_annotated=Count('flags', distinct=True)
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
        Comprehensive optimization for list views.
        Combines all common optimizations.
        """
        from .models import CommentFlag
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
            flags_count_annotated=Count('flags', distinct=True),
            children_count_annotated=Count('children', distinct=True)
        )
    
    def for_model(self, model_or_instance):
        """
        Return all comments for a specific model or model instance.
        OPTIMIZED: Includes basic optimizations.
        """
        if isinstance(model_or_instance, models.Model):
            # It's a model instance
            model = model_or_instance.__class__
            content_type = ContentType.objects.get_for_model(model)
            return self.filter(
                content_type=content_type,
                object_id=model_or_instance.pk
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
        OPTIMIZED: Includes basic optimizations.
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
        Return comments that have been flagged.
        OPTIMIZED: Uses annotation instead of extra queries.
        """
        return self.annotate(
            flag_count=Count('flags')
        ).filter(
            flag_count__gt=0
        ).with_user_and_content_type().with_flags()
    
    def root_nodes(self):
        """
        Return only root comments (no parent).
        OPTIMIZED: Includes basic optimizations.
        """
        return self.filter(
            parent__isnull=True
        ).with_user_and_content_type()
    
    def by_user(self, user):
        """
        Return comments by a specific user.
        OPTIMIZED: Includes basic optimizations.
        """
        return self.filter(user=user).with_user_and_content_type()
    
    def by_thread(self, thread_id):
        """
        Return comments belonging to a specific thread.
        OPTIMIZED: Includes basic optimizations.
        """
        return self.filter(
            thread_id=thread_id
        ).with_user_and_content_type().with_parent_info()
    
    def search(self, query):
        """
        Search for comments by content or username.
        OPTIMIZED: Includes basic optimizations.
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
        from .models import CommentFlag, Comment
        
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
            flags_count_annotated=Count('flags', distinct=True),
            children_count_annotated=Count('children', distinct=True)
        )


class CommentManager(models.Manager):
    """
    Custom Manager for Comment model.
    """
    
    def get_by_content_object(self, content_object):
        """
        Return all comments for a given object.
        OPTIMIZED version of common query pattern.
        """
        content_type = ContentType.objects.get_for_model(content_object)
        return self.filter(
            content_type=content_type,
            object_id=content_object.pk
        ).optimized_for_list()
    
    def get_by_model_and_id(self, model, object_id):
        """
        Return all comments for a given model and object_id.
        OPTIMIZED version.
        """
        content_type = ContentType.objects.get_for_model(model)
        return self.filter(
            content_type=content_type,
            object_id=object_id
        ).optimized_for_list()
    
    def create_for_object(self, content_object, **kwargs):
        """
        Create a new comment for a specific object.
        """
        content_type = ContentType.objects.get_for_model(content_object)
        return self.create(
            content_type=content_type,
            object_id=content_object.pk,
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
    Enhanced manager for CommentFlag with safe operations.
    """
    
    def create_or_get_flag(self, comment, user, flag, reason=''):
        """
        Create a flag or return existing one.
        Prevents duplicate flags and handles both Comment types.
        
        Args:
            comment: Comment or UUIDComment instance
            user: User who is flagging
            flag: Flag type ('spam', 'offensive', etc.)
            reason: Optional reason text
        
        Returns:
            tuple: (CommentFlag instance, created bool)
        
        Example:
            flag, created = CommentFlag.objects.create_or_get_flag(
                comment=my_comment,
                user=request.user,
                flag='spam',
                reason='This is clearly spam'
            )
        """
        # Get ContentType for the comment (works with both Comment types)
        comment_ct = ContentType.objects.get_for_model(comment)
        
        # Convert PK to string (works for int and UUID)
        comment_id_str = str(comment.pk)
        
        # Try to get or create
        flag_obj, created = self.get_or_create(
            comment_type=comment_ct,
            comment_id=comment_id_str,
            user=user,
            flag=flag,
            defaults={'reason': reason}
        )
        
        # If not created and reason is different, update it
        if not created and reason and flag_obj.reason != reason:
            flag_obj.reason = reason
            flag_obj.save(update_fields=['reason', 'updated_at'])
        
        return flag_obj, created
    
    def get_flags_for_comment(self, comment):
        """
        Get all flags for a specific comment.
        Works with both Comment and UUIDComment.
        
        Args:
            comment: Comment or UUIDComment instance
        
        Returns:
            QuerySet of CommentFlag instances
        
        Example:
            flags = CommentFlag.objects.get_flags_for_comment(my_comment)
            for flag in flags:
                print(f"{flag.user} flagged as {flag.flag}")
        """
        comment_ct = ContentType.objects.get_for_model(comment)
        return self.filter(
            comment_type=comment_ct,
            comment_id=str(comment.pk)
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
        from django.db.models import Count
        
        return self.values(
            'comment_type', 'comment_id'
        ).annotate(
            flag_count=Count('id')
        ).filter(
            flag_count__gte=min_flags
        ).order_by('-flag_count')