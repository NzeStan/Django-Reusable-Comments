"""
Factories for creating test data.
"""
import factory
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from factory.django import DjangoModelFactory

from ..models import Comment, CommentFlag
from .models import TestPost, TestPostWithUUID

User = get_user_model()


class UserFactory(DjangoModelFactory):
    """
    Factory for creating User instances.
    """
    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'password')
    
    class Meta:
        model = User
        django_get_or_create = ('username',)
        skip_postgeneration_save = True


class TestPostFactory(DjangoModelFactory):
    """
    Factory for creating TestPost instances.
    """
    title = factory.Sequence(lambda n: f'Test Post {n}')
    content = factory.Faker('paragraph', nb_sentences=5)
    
    class Meta:
        model = TestPost


class TestPostWithUUIDFactory(DjangoModelFactory):
    """
    Factory for creating TestPostWithUUID instances.
    """
    title = factory.Sequence(lambda n: f'Test Post UUID {n}')
    content = factory.Faker('paragraph', nb_sentences=5)
    
    class Meta:
        model = TestPostWithUUID


class CommentFactory(DjangoModelFactory):
    """
    Factory for creating Comment instances.
    """
    content = factory.Faker('paragraph', nb_sentences=3)
    user = factory.SubFactory(UserFactory)
    is_public = True
    is_removed = False
    
    # By default, create a comment for a TestPost
    content_type = factory.LazyAttribute(
        lambda _: ContentType.objects.get_for_model(TestPost)
    )
    object_id = factory.LazyAttribute(
        lambda o: TestPostFactory.create().id
    )
    
    class Meta:
        model = Comment
        skip_postgeneration_save = True
    
    @factory.post_generation
    def setup_thread(self, create, extracted, **kwargs):
        """
        Set up threading related fields.
        """
        if not create:
            return
            
        # Ensure path and thread_id are set
        if not self.path or not self.thread_id:
            if self.parent:
                self.path = f"{self.parent.path}/{self.pk}"
                self.thread_id = self.parent.thread_id
            else:
                self.path = str(self.pk)
                self.thread_id = str(self.pk)
            
            self.save(update_fields=['path', 'thread_id'])


class CommentFlagFactory(DjangoModelFactory):
    """
    Factory for creating CommentFlag instances.
    """
    comment = factory.SubFactory(CommentFactory)
    user = factory.SubFactory(UserFactory)
    flag = 'spam'
    reason = factory.Faker('sentence')
    
    class Meta:
        model = CommentFlag