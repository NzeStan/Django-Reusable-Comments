from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Count, Q

class CommentQuerySet(models.QuerySet):
    """
    Custom QuerySet for Comment model.
    """
    def for_model(self, model_or_instance):
        """
        Return all comments for a specific model or model instance.
        """
        if isinstance(model_or_instance, models.Model):
            # It's a model instance
            model = model_or_instance.__class__
            content_type = ContentType.objects.get_for_model(model)
            return self.filter(
                content_type=content_type,
                object_id=model_or_instance.pk
            )
        else:
            # It's a model class
            content_type = ContentType.objects.get_for_model(model_or_instance)
            return self.filter(content_type=content_type)
    
    def public(self):
        """
        Return only public, non-removed comments.
        """
        return self.filter(is_public=True, is_removed=False)
    
    def removed(self):
        """
        Return only removed comments.
        """
        return self.filter(is_removed=True)
    
    def not_public(self):
        """
        Return non-public comments (moderation queue).
        """
        return self.filter(is_public=False, is_removed=False)
    
    def flagged(self):
        """
        Return comments that have been flagged.
        """
        return self.annotate(flag_count=Count('flags')).filter(flag_count__gt=0)
    
    def root_nodes(self):
        """
        Return only root comments (no parent).
        """
        return self.filter(parent__isnull=True)
    
    def by_user(self, user):
        """
        Return comments by a specific user.
        """
        return self.filter(user=user)
    
    def by_thread(self, thread_id):
        """
        Return comments belonging to a specific thread.
        """
        return self.filter(thread_id=thread_id)
    
    def search(self, query):
        """
        Search for comments by content or username.
        """
        return self.filter(
            Q(content__icontains=query) | 
            Q(user_name__icontains=query) |
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query)
        )
    
    def create_with_flags(self, **kwargs):
        """
        Create a comment and flag it based on given flags.
        """
        flags = kwargs.pop('flags', [])
        comment = self.create(**kwargs)
        
        # Add flags if any were provided
        if flags and hasattr(comment, 'flags'):
            for flag_data in flags:
                comment.flags.create(**flag_data)
        
        return comment


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
            object_id=content_object.pk
        )
    
    def get_by_model_and_id(self, model, object_id):
        """
        Return all comments for a given model and object_id.
        """
        content_type = ContentType.objects.get_for_model(model)
        return self.filter(
            content_type=content_type,
            object_id=object_id
        )
    
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
    